"""SMS Campaign Worker — Kafka consumer that processes campaigns asynchronously.

Flow:
  1. Campaign service publishes to `sms.campaign.created` when user clicks "Send".
  2. This worker consumes that event.
  3. For each recipient, publishes individual `sms.message.send` events.
  4. A second handler processes `sms.message.send` events:
     - Calls the SMS Forwarding API (AkashSMS provider)
     - Publishes `sms.message.status.updated` with the result
  5. A third handler processes `sms.message.status.updated`:
     - Updates the SmsMessage row in the database
     - Recounts campaign aggregates

Run as a standalone process:
    python -m app.workers.sms_campaign_worker

CRITICAL: JSON payloads contain string UUIDs. asyncpg requires uuid.UUID
objects. Every ID from a payload MUST be converted with uuid.UUID() before
touching the database. This is the #1 source of silent failures.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _to_uuid(value) -> uuid.UUID:
    """Safely convert a string or UUID to uuid.UUID.
    asyncpg REQUIRES uuid.UUID objects — passing strings causes silent failures.
    """
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _to_str(value, max_len: int = 1000) -> str | None:
    """Defensively coerce any value into a plain string for VARCHAR columns.

    asyncpg will reject non-str Python objects (lists, dicts) bound to a
    VARCHAR column with 'expected str, got list/dict'. Providers are expected
    to already return strings (see akashsms_provider._stringify_error), but
    this is a second safety net at the DB-write boundary so a future provider
    bug never crashes message-status processing again.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value[:max_len]
    try:
        return json.dumps(value)[:max_len]
    except (TypeError, ValueError):
        return str(value)[:max_len]


# ═══════════════════════════════════════════════════════════════════════════════
# Handler 1: sms.campaign.created — resolve recipients, fan-out messages
# ═══════════════════════════════════════════════════════════════════════════════

async def process_campaign_created(
    payload: dict,
    db_url: str,
    forwarding_url: str,
    forwarding_key: str,
    kafka_servers: str,
) -> None:
    """Handle sms.campaign.created — resolve recipients and fan-out messages."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.constants import SmsCampaignSource, SmsCampaignStatus, SmsMessageStatus
    from app.core.kafka import KafkaTopics, PlatformProducer
    from app.models.sms import SmsCampaign, SmsCampaignRecipient, SmsMessage
    from app.repositories.contact_list_repository import ContactListRepository
    from app.repositories.contact_repository import ContactRepository
    from app.repositories.sms_campaign_repository import (
        SmsCampaignRecipientRepository,
        SmsCampaignRepository,
        SmsMessageRepository,
    )
    from app.repositories.sms_repository import SmsSenderIdRepository, SmsTemplateRepository
    from app.services.sms_recipient_resolver import SmsRecipientResolver
    from app.services import sms_renderer

    # ── STEP 0: Parse and convert UUIDs from JSON payload ──
    try:
        campaign_id = _to_uuid(payload["campaign_id"])
        company_id = _to_uuid(payload["company_id"])
    except (KeyError, ValueError) as e:
        logger.error("Invalid payload — missing or malformed UUID: %s", e)
        return

    logger.info("[campaign=%s] Step 0: Payload parsed. company=%s", campaign_id, company_id)

    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        try:
            # ── STEP 1: Build tenant context ──
            from app.core.rbac import TenantContext, resolve_permissions

            ctx = TenantContext(
                user_id=payload.get("actor_id", str(uuid.uuid4())),
                company_id=str(company_id),  # TenantContext.company_id is str
                roles=["company_admin"],
                permissions=resolve_permissions(["company_admin"]),
            )

            campaigns = SmsCampaignRepository(session, ctx)
            recipients_repo = SmsCampaignRecipientRepository(session, ctx)
            messages_repo = SmsMessageRepository(session, ctx)
            senders = SmsSenderIdRepository(session, ctx)
            templates = SmsTemplateRepository(session, ctx)

            logger.info("[campaign=%s] Step 1: Tenant context built", campaign_id)

            # ── STEP 2: Load campaign ──
            campaign = await campaigns.get_by_id(campaign_id)
            if campaign is None:
                logger.error("[campaign=%s] Step 2: FAILED — campaign not found", campaign_id)
                return

            logger.info(
                "[campaign=%s] Step 2: Campaign loaded. status=%s, sender_id=%s, template_id=%s",
                campaign_id, campaign.status, campaign.sender_id, campaign.template_id,
            )

            if campaign.status != SmsCampaignStatus.PROCESSING.value:
                logger.warning(
                    "[campaign=%s] Step 2: SKIP — status=%s, expected 'processing'",
                    campaign_id, campaign.status,
                )
                return

            # ── STEP 3: Load sender and template ──
            sender = await senders.get_by_id(campaign.sender_id) if campaign.sender_id else None
            template = await templates.get_by_id(campaign.template_id) if campaign.template_id else None

            if not sender:
                logger.error("[campaign=%s] Step 3: FAILED — sender not found (id=%s)", campaign_id, campaign.sender_id)
                await campaigns.update(campaign, status=SmsCampaignStatus.FAILED.value)
                await session.commit()
                return
            if not template:
                logger.error("[campaign=%s] Step 3: FAILED — template not found (id=%s)", campaign_id, campaign.template_id)
                await campaigns.update(campaign, status=SmsCampaignStatus.FAILED.value)
                await session.commit()
                return

            logger.info(
                "[campaign=%s] Step 3: Sender '%s' and template '%s' loaded",
                campaign_id, sender.sender_id, template.name,
            )

            # ── STEP 4: Resolve recipients ──
            resolver = SmsRecipientResolver(
                ContactRepository(session, ctx),
                ContactListRepository(session, ctx),
            )

            if campaign.source_type == SmsCampaignSource.CONTACT_LIST.value:
                resolved = await resolver.resolve(
                    source_type=campaign.source_type,
                    source_list_id=campaign.source_list_id,
                )
            else:
                existing_recipients = await recipients_repo.all_for_campaign(campaign_id)
                contact_ids = [
                    r.contact_id for r in existing_recipients
                    if r.contact_id is not None
                ]
                resolved = await resolver.resolve(
                    source_type=campaign.source_type,
                    contact_ids=contact_ids,
                )

            logger.info("[campaign=%s] Step 4: Resolved %d recipients", campaign_id, len(resolved))

            if not resolved:
                logger.warning("[campaign=%s] Step 4: No recipients resolved — marking failed", campaign_id)
                await campaigns.update(
                    campaign,
                    status=SmsCampaignStatus.FAILED.value,
                    total_recipients=0,
                )
                await session.commit()
                return

            # ── STEP 5: Freeze recipients ──
            await recipients_repo.delete_for_campaign(campaign_id)
            await recipients_repo.bulk_add([
                {
                    "campaign_id": campaign_id,    # uuid.UUID ✓
                    "contact_id": r.contact_id,    # uuid.UUID or None ✓
                    "phone_e164": r.phone_e164,
                    "resolved_name": r.resolved_name,
                }
                for r in resolved
            ])

            logger.info("[campaign=%s] Step 5: Recipients frozen", campaign_id)

            # ── STEP 6: Get company name for template rendering ──
            from sqlalchemy import select
            from app.models.company import Company

            company_name = (await session.execute(
                select(Company.name).where(Company.id == company_id)
            )).scalar_one_or_none()

            logger.info("[campaign=%s] Step 6: Company name = %s", campaign_id, company_name)

            # ── STEP 7: Start Kafka producer for per-message events ──
            producer = PlatformProducer(kafka_servers)
            await producer.start()

            logger.info(
                "[campaign=%s] Step 7: Kafka producer started (connected=%s)",
                campaign_id, producer.is_connected,
            )

            # ── STEP 8: Build messages and publish send events ──
            now = datetime.now(timezone.utc)
            total = len(resolved)
            message_rows = []

            for i, r in enumerate(resolved, 1):
                try:
                    content = sms_renderer.render_template(
                        template.body,
                        sms_renderer.build_recipient_values(
                            name=r.resolved_name,
                            phone=r.phone_e164,
                            company=company_name,
                        ),
                    )
                except Exception as render_err:
                    logger.error(
                        "[campaign=%s] Step 8: Template render FAILED for recipient %d: %s",
                        campaign_id, i, render_err,
                    )
                    content = template.body  # fallback: raw template

                msg_id = uuid.uuid4()

                # ALL values must be proper Python types for asyncpg:
                #   UUIDs → uuid.UUID objects (NOT strings)
                #   strings → str
                #   ints → int
                message_rows.append({
                    "id": msg_id,                     # uuid.UUID ✓
                    "company_id": company_id,          # uuid.UUID ✓ (converted at top)
                    "campaign_id": campaign_id,        # uuid.UUID ✓ (converted at top)
                    "recipient_phone": r.phone_e164,
                    "sender_id": sender.sender_id,     # str ✓
                    "content": content,
                    "status": SmsMessageStatus.QUEUED.value,
                })

                # Publish per-message send event (string UUIDs OK for JSON/Kafka)
                await producer.produce(
                    KafkaTopics.SMS_MESSAGE_SEND,
                    key=str(company_id),
                    value={
                        "message_id": str(msg_id),
                        "campaign_id": str(campaign_id),
                        "company_id": str(company_id),
                        "recipient_phone": r.phone_e164,
                        "content": content,
                        "sender_id": sender.sender_id,
                    },
                )

            logger.info(
                "[campaign=%s] Step 8: %d messages built, %d Kafka events published",
                campaign_id, len(message_rows), len(message_rows),
            )

            # ── STEP 9: Bulk insert message rows ──
            await messages_repo.bulk_add(message_rows)

            logger.info("[campaign=%s] Step 9: %d SmsMessage rows flushed to session", campaign_id, len(message_rows))

            # ── STEP 10: Update campaign counters and commit ──
            await campaigns.update(campaign, total_recipients=total)
            await session.commit()

            logger.info("[campaign=%s] Step 10: Transaction committed. %d messages queued.", campaign_id, total)

            await producer.stop()

            logger.info(
                "[campaign=%s] ✅ COMPLETE — %d messages queued for delivery",
                campaign_id, total,
            )

        except Exception as exc:
            logger.error(
                "[campaign=%s] ❌ EXCEPTION at processing stage:\n%s",
                campaign_id, traceback.format_exc(),
            )

            # Attempt to mark campaign as failed using a FRESH session
            # (the current session may be in an error state after a flush failure)
            try:
                await session.rollback()
            except Exception:
                pass

            try:
                async with Session() as recovery_session:
                    from sqlalchemy import update as sa_update
                    await recovery_session.execute(
                        sa_update(SmsCampaign)
                        .where(SmsCampaign.id == campaign_id)
                        .where(SmsCampaign.status == SmsCampaignStatus.PROCESSING.value)
                        .values(status=SmsCampaignStatus.FAILED.value)
                    )
                    await recovery_session.commit()
                    logger.info("[campaign=%s] Recovery: status set to FAILED", campaign_id)
            except Exception as recovery_err:
                logger.error(
                    "[campaign=%s] Recovery ALSO failed: %s", campaign_id, recovery_err,
                )

            raise

    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Handler 2: sms.message.send — call SMS Forwarding API, publish status
# ═══════════════════════════════════════════════════════════════════════════════

async def process_message_send(
    payload: dict,
    forwarding_url: str,
    forwarding_key: str,
    kafka_servers: str,
) -> None:
    """Handle sms.message.send — call SMS Forwarding API, publish status."""
    from app.core.kafka import KafkaTopics, PlatformProducer
    from app.services.akashsms_provider import AkashSmsProvider

    message_id = payload["message_id"]
    logger.info("[message=%s] Sending via SMS Forwarding API...", message_id)

    provider = AkashSmsProvider(forwarding_url, forwarding_key)

    result = await provider.send_async(
        recipient_phone=payload["recipient_phone"],
        content=payload["content"],
        sender_id=payload.get("sender_id"),
    )

    logger.info(
        "[message=%s] Forwarding API result: status=%s, provider_id=%s, error=%s",
        message_id, result.status, result.provider_message_id, result.error_details,
    )

    # Publish status update
    producer = PlatformProducer(kafka_servers)
    await producer.start()

    await producer.produce(
        KafkaTopics.SMS_MESSAGE_STATUS,
        key=payload.get("company_id", ""),
        value={
            "message_id": message_id,
            "campaign_id": payload.get("campaign_id"),
            "company_id": payload.get("company_id"),
            "status": result.status,
            "provider_message_id": result.provider_message_id,
            "error_details": result.error_details,
        },
    )
    await producer.stop()

    logger.info("[message=%s] Status event published: %s", message_id, result.status)


# ═══════════════════════════════════════════════════════════════════════════════
# Handler 3: sms.message.status.updated — update DB, recount campaign
# ═══════════════════════════════════════════════════════════════════════════════

async def process_message_status(
    payload: dict,
    db_url: str,
) -> None:
    """Handle sms.message.status.updated — update DB, recount campaign."""
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.constants import SmsMessageStatus, SmsCampaignStatus
    from app.models.sms import SmsCampaign, SmsMessage

    # Convert UUIDs from JSON strings
    try:
        message_id = _to_uuid(payload["message_id"])
    except (KeyError, ValueError) as e:
        logger.error("Invalid status payload — bad message_id: %s", e)
        return

    new_status = payload["status"]
    campaign_id_raw = payload.get("campaign_id")
    now = datetime.now(timezone.utc)

    logger.info("[message=%s] Processing status update: %s", message_id, new_status)

    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Update message
        msg = (await session.execute(
            select(SmsMessage).where(SmsMessage.id == message_id)
        )).scalar_one_or_none()

        if msg is None:
            logger.warning("[message=%s] Not found in DB — skipping status update", message_id)
            await engine.dispose()
            return

        msg.status = new_status
        if payload.get("provider_message_id"):
            msg.provider_message_id = payload["provider_message_id"]
        if payload.get("error_details"):
            msg.error_details = _to_str(payload["error_details"])
        if new_status == "sent":
            msg.sent_at = now
        elif new_status == "delivered":
            msg.delivered_at = now
            if not msg.sent_at:
                msg.sent_at = now

        await session.flush()
        logger.info("[message=%s] DB row updated to status=%s", message_id, new_status)

        # Recount campaign
        if campaign_id_raw:
            try:
                campaign_uuid = _to_uuid(campaign_id_raw)
            except ValueError:
                campaign_uuid = None

            if campaign_uuid:
                rows = (await session.execute(
                    select(SmsMessage.status, func.count())
                    .where(SmsMessage.campaign_id == campaign_uuid)
                    .group_by(SmsMessage.status)
                )).all()

                counts = {s: int(n) for s, n in rows}
                sent = counts.get("sent", 0) + counts.get("delivered", 0)
                delivered = counts.get("delivered", 0)
                failed = counts.get("failed", 0)
                queued = counts.get("queued", 0)
                total = sum(counts.values())

                campaign = (await session.execute(
                    select(SmsCampaign).where(SmsCampaign.id == campaign_uuid)
                )).scalar_one_or_none()

                if campaign:
                    campaign.sent_count = sent
                    campaign.delivered_count = delivered
                    campaign.failed_count = failed

                    if queued == 0 and campaign.status == SmsCampaignStatus.PROCESSING.value:
                        if failed == total:
                            campaign.status = SmsCampaignStatus.FAILED.value
                        else:
                            campaign.status = SmsCampaignStatus.COMPLETED.value
                        logger.info(
                            "[campaign=%s] Auto-completed: status=%s (sent=%d delivered=%d failed=%d)",
                            campaign_uuid, campaign.status, sent, delivered, failed,
                        )

        await session.commit()
        logger.info("[message=%s] Status update committed", message_id)

    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Worker entry point
# ═══════════════════════════════════════════════════════════════════════════════

class SmsCampaignConsumer:
    """Unified consumer handling all three SMS topics."""

    def __init__(
        self,
        kafka_servers: str,
        db_url: str,
        forwarding_url: str,
        forwarding_key: str,
    ):
        self.kafka_servers = kafka_servers
        self.db_url = db_url
        self.forwarding_url = forwarding_url
        self.forwarding_key = forwarding_key

    async def run(self) -> None:
        from app.core.kafka import KafkaTopics, KafkaMessage, PlatformConsumer, PlatformProducer

        worker = self

        class _Consumer(PlatformConsumer):
            async def handle(self, message: KafkaMessage) -> None:
                logger.info(
                    "Received message: topic=%s message_id=%s",
                    message.topic, message.message_id,
                )
                if message.topic == KafkaTopics.SMS_CAMPAIGN_CREATED:
                    await process_campaign_created(
                        message.payload,
                        worker.db_url,
                        worker.forwarding_url,
                        worker.forwarding_key,
                        worker.kafka_servers,
                    )
                elif message.topic == KafkaTopics.SMS_MESSAGE_SEND:
                    await process_message_send(
                        message.payload,
                        worker.forwarding_url,
                        worker.forwarding_key,
                        worker.kafka_servers,
                    )
                elif message.topic == KafkaTopics.SMS_MESSAGE_STATUS:
                    await process_message_status(
                        message.payload,
                        worker.db_url,
                    )
                else:
                    logger.warning("Unknown topic: %s", message.topic)

        producer = PlatformProducer(self.kafka_servers)
        await producer.start()

        consumer = _Consumer(
            bootstrap_servers=self.kafka_servers,
            topics=[
                KafkaTopics.SMS_CAMPAIGN_CREATED,
                KafkaTopics.SMS_MESSAGE_SEND,
                KafkaTopics.SMS_MESSAGE_STATUS,
            ],
            group_id="sms-campaign-workers",
            producer=producer,
        )

        try:
            await consumer.run()
        finally:
            await producer.stop()


def main():
    """CLI entry point: python -m app.workers.sms_campaign_worker

    Runs the consumer in a restart loop: if consumer.run() ever raises an
    unhandled exception (e.g. a Kafka error not caught by the internal
    rebalance guards), log it and restart the consumer after a short delay
    instead of letting the whole worker process die. This is the outermost
    safety net — the in-loop fixes in PlatformConsumer.run() should prevent
    most of these, but this guarantees the worker keeps running regardless.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from app.core.config import settings

    logger.info("Starting SMS Campaign Worker...")
    logger.info("  Kafka: %s", settings.KAFKA_BOOTSTRAP_SERVERS)
    logger.info("  DB: %s", settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured")
    logger.info("  Forwarding API: %s", settings.SMS_FORWARDING_API_URL)

    restart_delay = 5  # seconds
    while True:
        consumer = SmsCampaignConsumer(
            kafka_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            db_url=settings.DATABASE_URL,
            forwarding_url=settings.SMS_FORWARDING_API_URL,
            forwarding_key=settings.SMS_FORWARDING_API_KEY,
        )
        try:
            asyncio.run(consumer.run())
            # run() returning normally means stop() was called deliberately —
            # exit the restart loop instead of looping forever.
            logger.info("Worker stopped normally.")
            break
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user (Ctrl+C). Shutting down.")
            break
        except Exception:
            logger.error(
                "Worker crashed with an unhandled exception:\n%s",
                traceback.format_exc(),
            )
            logger.info("Restarting worker in %d seconds...", restart_delay)
            import time
            time.sleep(restart_delay)


if __name__ == "__main__":
    main()