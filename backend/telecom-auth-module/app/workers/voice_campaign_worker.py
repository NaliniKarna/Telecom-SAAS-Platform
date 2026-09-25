"""Voice Campaign Execution Worker (Phase 4B).

Flow, one Kafka message = one recipient execution attempt:

    voice.campaign.recipient.execute
      -> claim the attempt (VoiceCampaignRecipientAttempt, unique execution_key)
      -> verify recipient/campaign/company ownership from the DB (never
         trust the event's company_id alone)
      -> atomically claim the recipient row (queued -> processing)
      -> TTS (existing TTSService/provider; skipped if audio already exists —
         idempotent on redelivery)
      -> store audio (existing FileStorage, via TTSService); consume TTS
         quota for the ACTUAL character count (Phase 4A's reservation model)
      -> resolve the company's PBX connection (existing
         TelephonyConnectionRepository.resolve_effective — the Phase 3 seam
         built for exactly this)
      -> originate_playback via the existing AsteriskProvider seam
      -> map the result onto the recipient/attempt status
      -> ask VoiceCampaignService to roll up the campaign aggregate if this
         was the last recipient to finish

Mirrors app.workers.sms_campaign_worker's shape and conventions exactly
(module-level handler functions directly callable/testable without a live
Kafka broker, a thin Consumer class, the same restart-loop main()) — see
that file's docstring for the asyncpg-UUID-conversion warning, which applies
here identically.

Run as a standalone process:
    python -m app.workers.voice_campaign_worker
"""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.workers.sms_campaign_worker import _to_str, _to_uuid

logger = logging.getLogger(__name__)


def _is_transient_tts_error(exc: Exception) -> bool:
    """Transient (worth a bounded retry) vs permanent (won't be fixed by
    retrying the exact same request) TTS provider failure. See
    ElevenLabsProviderError.status_code's docstring for the exact rule.
    Unknown exception types default to transient — if genuinely permanent,
    the bounded retry loop below simply exhausts and the recipient is marked
    FAILED with the real error recorded, never silently swallowed either way.
    """
    from app.services.elevenlabs_provider import ElevenLabsProviderError

    if isinstance(exc, ElevenLabsProviderError):
        if exc.status_code is None:
            return True
        return exc.status_code >= 500
    return True


MAX_TTS_ATTEMPTS = 3
TTS_RETRY_BACKOFF_BASE = 2.0


async def _generate_and_store_audio(tts_service, *, text: str, provider_voice_id: str, storage_prefix: str):
    """Bounded retry around the (synchronous, blocking) TTS call — run off
    the event loop via asyncio.to_thread so one recipient's HTTP call to
    ElevenLabs (or local disk I/O for the Null provider) never stalls the
    whole consumer. Raises the last exception if every attempt fails."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_TTS_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(
                tts_service.synthesize_and_store,
                text=text, provider_voice_id=provider_voice_id, storage_prefix=storage_prefix,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            transient = _is_transient_tts_error(exc)
            if transient and attempt < MAX_TTS_ATTEMPTS:
                wait = TTS_RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "tts_retry attempt=%d/%d transient=%s wait=%.1fs error=%s",
                    attempt, MAX_TTS_ATTEMPTS, transient, wait, exc,
                )
                await asyncio.sleep(wait)
                continue
            logger.error(
                "tts_failed attempt=%d/%d transient=%s error=%s",
                attempt, MAX_TTS_ATTEMPTS, transient, exc,
            )
            raise
    raise last_exc  # pragma: no cover — loop always returns or raises above


async def _resolve_pbx_connection_params(session, company_id):
    """Reuses the Phase 3 seam built for exactly this (resolve_effective's
    own docstring: 'kept for Voice / Missed-Call (Phase 5/6) per-tenant
    routing'). Returns (ConnectionParams, source) or (None, "none") if no
    usable connection is configured."""
    from app.core.config import settings
    from app.core.crypto import decrypt_secret
    from app.repositories.telephony_repository import TelephonyConnectionRepository
    from app.services.asterisk_provider import ConnectionParams

    repo = TelephonyConnectionRepository(session)
    source, conn = await repo.resolve_effective(company_id)
    if conn is None or not conn.enabled:
        return None, source
    try:
        secret = decrypt_secret(conn.ami_secret_encrypted)
    except ValueError as exc:
        logger.error("pbx_secret_decrypt_failed company_id=%s error=%s", company_id, exc)
        return None, source
    return ConnectionParams(
        host=conn.host, port=conn.port, username=conn.ami_username, secret=secret,
        use_tls=conn.use_tls, timeout=settings.TELEPHONY_CONNECT_TIMEOUT,
    ), source


async def process_recipient_execution(payload: dict, db_url: str) -> None:
    """Handle one voice.campaign.recipient.execute event end to end."""
    from app.core.constants import VoiceCampaignRecipientStatus, VoiceCampaignStatus
    from app.core.rbac import TenantContext, resolve_permissions
    from app.models.ai_voice import AiVoice
    from app.repositories.voice_campaign_repository import (
        VoiceCampaignAudioRepository,
        VoiceCampaignRecipientAttemptRepository,
        VoiceCampaignRecipientRepository,
        VoiceCampaignRepository,
    )
    from app.services.asterisk_provider import (
        OriginatePlaybackParams,
        get_asterisk_provider,
    )
    from app.services.tts_service import TTSService
    from app.services.voice_campaign_service import VoiceCampaignService, execution_key

    try:
        company_id_claimed = _to_uuid(payload["company_id"])
        campaign_id = _to_uuid(payload["campaign_id"])
        recipient_id = _to_uuid(payload["recipient_id"])
        attempt_number = int(payload["attempt_number"])
        exec_key = str(payload["execution_key"])
    except (KeyError, ValueError, TypeError) as exc:
        logger.error("voice_execution_malformed_payload error=%s payload=%s", exc, payload)
        return  # ack — a malformed event can never succeed by retrying

    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        try:
            attempts_repo = VoiceCampaignRecipientAttemptRepository(session)
            attempt = await attempts_repo.try_claim(
                recipient_id=recipient_id, attempt_number=attempt_number, execution_key=exec_key,
            )
            if attempt is None:
                logger.info(
                    "voice_execution_duplicate execution_key=%s recipient_id=%s — already claimed, skipping",
                    exec_key, recipient_id,
                )
                return
            await session.commit()

            # ── Verify recipient/campaign/company ownership from the DB —
            # never trust the event's company_id alone (spec section 16). ──
            recipient = await VoiceCampaignRecipientRepository(session).get_by_id_unscoped(recipient_id)
            if recipient is None or recipient.campaign_id != campaign_id:
                await attempts_repo.update(
                    attempt, status="failed", ended_at=datetime.now(timezone.utc),
                    failure_reason="recipient not found or campaign_id mismatch",
                )
                await session.commit()
                logger.error(
                    "voice_execution_recipient_mismatch recipient_id=%s campaign_id=%s",
                    recipient_id, campaign_id,
                )
                return

            campaign = await VoiceCampaignRepository(session, None).get_by_id(campaign_id)
            if campaign is None or campaign.company_id != company_id_claimed:
                await attempts_repo.update(
                    attempt, status="failed", ended_at=datetime.now(timezone.utc),
                    failure_reason="campaign not found or company_id mismatch — event distrusted",
                )
                await session.commit()
                logger.error(
                    "voice_execution_tenant_mismatch campaign_id=%s claimed_company=%s",
                    campaign_id, company_id_claimed,
                )
                return
            company_id = campaign.company_id  # the VERIFIED id, not the claimed one, from here on

            if campaign.status != VoiceCampaignStatus.PROCESSING.value:
                await attempts_repo.update(
                    attempt, status="failed", ended_at=datetime.now(timezone.utc),
                    failure_reason=f"campaign status is '{campaign.status}', not processing — skipped",
                )
                await session.commit()
                logger.info(
                    "voice_execution_campaign_not_processing campaign_id=%s status=%s",
                    campaign_id, campaign.status,
                )
                return

            ctx = TenantContext(
                user_id=str(uuid.uuid4()), company_id=str(company_id),
                roles=["company_admin"], permissions=resolve_permissions(["company_admin"]),
            )
            service = VoiceCampaignService(session, ctx)

            # ── Atomically claim the recipient (queued -> processing). Only
            # one worker's UPDATE matches; a stale/duplicate claim safely
            # exits (spec section 14). ──
            claimed = await service.recipients.try_claim_for_processing(
                recipient_id, allowed_from=[VoiceCampaignRecipientStatus.QUEUED.value],
                expected_attempt=attempt_number,
            )
            if claimed is None:
                await attempts_repo.update(
                    attempt, status="failed", ended_at=datetime.now(timezone.utc),
                    failure_reason="recipient already claimed by another attempt/worker",
                )
                await session.commit()
                logger.info(
                    "voice_execution_recipient_already_claimed recipient_id=%s attempt=%d",
                    recipient_id, attempt_number,
                )
                return
            recipient = claimed
            await session.commit()

            audios_repo = VoiceCampaignAudioRepository(session)

            # ── TTS (skip entirely if this recipient already has audio —
            # idempotent on redelivery after a crash post-consume). ──
            audio = None
            if recipient.audio_id is not None:
                audio = await audios_repo.get_by_id(recipient.audio_id)
            if audio is None:
                voice = (await session.execute(
                    select(AiVoice).where(AiVoice.id == campaign.resolved_voice_id)
                )).scalar_one_or_none()
                if voice is None:
                    recipient.status = VoiceCampaignRecipientStatus.FAILED.value
                    recipient.error_message = "Campaign's resolved voice no longer exists"
                    await attempts_repo.update(
                        attempt, status="failed", ended_at=datetime.now(timezone.utc),
                        failure_reason=recipient.error_message,
                    )
                    await session.commit()
                    await service.finalize_if_done(campaign_id)
                    return

                tts_service = TTSService()
                try:
                    result = await _generate_and_store_audio(
                        tts_service, text=recipient.rendered_text,
                        provider_voice_id=voice.provider_voice_id,
                        storage_prefix=f"voice-campaigns/{company_id}/{campaign_id}",
                    )
                except Exception as exc:  # noqa: BLE001 — permanent or exhausted-transient
                    recipient.status = VoiceCampaignRecipientStatus.FAILED.value
                    recipient.error_message = _to_str(str(exc))
                    await attempts_repo.update(
                        attempt, status="failed", ended_at=datetime.now(timezone.utc),
                        failure_reason=_to_str(str(exc), max_len=500),
                    )
                    await session.commit()
                    await service.finalize_if_done(campaign_id)
                    return

                audio = await audios_repo.create(
                    company_id=company_id, campaign_id=campaign_id, recipient_id=recipient.id,
                    storage_url=result.audio_url, content_type=result.content_type,
                    duration_seconds=result.duration_seconds, char_count=result.char_count,
                    provider=voice.provider, storage_backend="local", pbx_reachable=False,
                )
                # Reconciliation: consume the ACTUAL character count against
                # the campaign's single reservation, not blindly the
                # original per-recipient estimate (spec section 6) — see
                # TtsUsageService.consume()'s clamp-to-remaining behavior for
                # why this can never push the monthly ceiling over its limit
                # even if actual > estimate for this recipient.
                await service.usage.consume(
                    reference_type="voice_campaign", reference_id=campaign_id,
                    characters=result.char_count,
                )
                recipient.audio_id = audio.id
                await attempts_repo.update(attempt, tts_char_count=result.char_count)
                await session.commit()

            # ── PBX origination ──
            recipient.status = VoiceCampaignRecipientStatus.CALLING.value
            await attempts_repo.update(
                attempt, status=VoiceCampaignRecipientStatus.CALLING.value,
                started_at=datetime.now(timezone.utc),
            )
            await session.commit()

            conn_params, pbx_source = await _resolve_pbx_connection_params(session, company_id)
            if conn_params is None:
                recipient.status = VoiceCampaignRecipientStatus.FAILED.value
                recipient.error_message = "No PBX connection configured for this company"
                await attempts_repo.update(
                    attempt, status="failed", ended_at=datetime.now(timezone.utc),
                    failure_reason=recipient.error_message,
                )
                await session.commit()
                await service.finalize_if_done(campaign_id)
                return

            provider = get_asterisk_provider()
            playback_params = OriginatePlaybackParams(
                destination_e164=recipient.phone_e164, audio_reference=audio.storage_url,
                campaign_id=str(campaign_id), recipient_id=str(recipient.id),
                correlation_id=exec_key,
            )
            result = await provider.originate_playback(conn_params, playback_params)

            now = datetime.now(timezone.utc)
            if not result.accepted:
                recipient.status = VoiceCampaignRecipientStatus.FAILED.value
                recipient.error_message = _to_str(result.error) or "Origination not accepted"
                await attempts_repo.update(
                    attempt, status="failed", ended_at=now,
                    provider_call_id=result.action_id, failure_reason=recipient.error_message,
                )
            elif result.final_status is not None:
                # Null/Simulator provider: whole call lifecycle already known.
                recipient.status = result.final_status
                attempt_fields = {
                    "status": result.final_status, "ended_at": now,
                    "provider_call_id": result.action_id,
                }
                if result.final_status == VoiceCampaignRecipientStatus.COMPLETED.value:
                    attempt_fields["answered_at"] = now
                await attempts_repo.update(attempt, **attempt_fields)
            else:
                # Real AMI seam: origination accepted, true outcome unknown —
                # stays at CALLING (spec: keep the state model honest; no
                # event listener exists yet to advance this further).
                await attempts_repo.update(attempt, provider_call_id=result.action_id)

            await session.commit()
            await service.finalize_if_done(campaign_id)

        except Exception:
            logger.error(
                "voice_execution_unhandled_exception execution_key=%s recipient_id=%s:\n%s",
                exec_key, recipient_id, traceback.format_exc(),
            )
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise  # let PlatformConsumer's retry/backoff/DLQ handle it

    await engine.dispose()


class VoiceCampaignConsumer:
    """Kafka consumer for the Phase 4B execution topic."""

    def __init__(self, kafka_servers: str, db_url: str):
        self.kafka_servers = kafka_servers
        self.db_url = db_url

    async def run(self) -> None:
        from app.core.kafka import KafkaMessage, KafkaTopics, PlatformConsumer, PlatformProducer

        worker = self

        class _Consumer(PlatformConsumer):
            async def handle(self, message: KafkaMessage) -> None:
                logger.info(
                    "voice_execution_received topic=%s message_id=%s",
                    message.topic, message.message_id,
                )
                if message.topic == KafkaTopics.VOICE_CAMPAIGN_RECIPIENT_EXECUTE:
                    await process_recipient_execution(message.payload, worker.db_url)
                else:
                    logger.warning("voice_execution_unknown_topic topic=%s", message.topic)

        producer = PlatformProducer(self.kafka_servers)
        await producer.start()

        consumer = _Consumer(
            bootstrap_servers=self.kafka_servers,
            topics=[KafkaTopics.VOICE_CAMPAIGN_RECIPIENT_EXECUTE],
            group_id="voice-campaign-workers",
            producer=producer,
        )
        try:
            await consumer.run()
        finally:
            await producer.stop()


def main():
    """CLI entry point: python -m app.workers.voice_campaign_worker

    Same outermost restart-loop safety net as sms_campaign_worker.main() —
    see that function's docstring.
    """
    import os
    import time as time_mod

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from app.core.config import settings

    logger.info("Starting Voice Campaign Execution Worker...")
    logger.info("  Kafka: %s", settings.KAFKA_BOOTSTRAP_SERVERS)
    logger.info("  DB: %s", settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured")
    logger.info("  Telephony provider: %s", settings.TELEPHONY_PROVIDER)
    logger.info("  TTS provider: %s", settings.TTS_PROVIDER)

    restart_delay = 5
    while True:
        consumer = VoiceCampaignConsumer(
            kafka_servers=settings.KAFKA_BOOTSTRAP_SERVERS, db_url=settings.DATABASE_URL,
        )
        try:
            asyncio.run(consumer.run())
            logger.info("Worker stopped normally.")
            break
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user (Ctrl+C). Shutting down.")
            break
        except Exception:
            logger.error("Worker crashed with an unhandled exception:\n%s", traceback.format_exc())
            logger.info("Restarting worker in %d seconds...", restart_delay)
            time_mod.sleep(restart_delay)


if __name__ == "__main__":
    main()
