"""Voice Campaign Foundation service (Phase 4A).

Reuses, rather than duplicates:
  - SmsRecipientResolver          for contact-list -> frozen recipient set
  - app.services.sms_renderer     for {{variable}} rendering
  - TtsUsageService                for the reserve/consume/release quota engine
  - AiVoiceRepository.get_visible_to_company()  for voice active+plan checks
  - existing VoiceTemplateRepository (from ai_voice_repository.py)

Campaign lifecycle: DRAFT -> (Start) -> PROCESSING -> ... (Phase 4B owns
everything after PROCESSING). This service only ever writes DRAFT,
PROCESSING, or CANCELLED — COMPLETED/FAILED/PARTIALLY_COMPLETED are Phase
4B's to set, once real execution exists.

The Start boundary (start_campaign) is the one method in this file that
matters most: see its docstring for the exact atomicity/idempotency
contract.
"""
from __future__ import annotations

import logging
import uuid as uuid_lib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    SmsCampaignSource,
    VOICE_CAMPAIGN_CANCELLABLE_STATUSES,
    VoiceCampaignRecipientStatus,
    VoiceCampaignStatus,
    VoiceStatus,
    VoiceTemplateStatus,
)
from app.core.exceptions import CompanyInactiveError, NotFoundError, ValidationError
from app.core.kafka import KafkaTopics, get_producer
from app.models.voice_campaign import VoiceCampaign, VoiceCampaignRecipient
from app.repositories.ai_voice_repository import AiVoiceRepository, VoiceTemplateRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.voice_campaign_repository import (
    VoiceCampaignRecipientRepository,
    VoiceCampaignRepository,
)
from app.services.audit_service import AuditService
from app.services.sms_recipient_resolver import SmsRecipientResolver
from app.services.sms_renderer import (
    build_recipient_values,
    missing_variables,
    render_template,
)
from app.services.tts_usage_service import TtsUsageService, UsageSummary

logger = logging.getLogger(__name__)

_CAMPAIGN_ENTITY = "voice_campaign"
_RECIPIENT_ENTITY = "voice_campaign_recipient"

# Recipient statuses this phase considers "done, no further automatic work" —
# used by both the aggregate rollup (finalize_if_done) and retry_recipient's
# allowed-from set. COMPLETED is deliberately excluded from the retryable set
# (spec: "retrying a successful recipient must not create another call").
_TERMINAL_RECIPIENT_STATUSES = frozenset([
    VoiceCampaignRecipientStatus.COMPLETED.value,
    VoiceCampaignRecipientStatus.NO_ANSWER.value,
    VoiceCampaignRecipientStatus.BUSY.value,
    VoiceCampaignRecipientStatus.FAILED.value,
])
_RETRYABLE_RECIPIENT_STATUSES = frozenset([
    VoiceCampaignRecipientStatus.NO_ANSWER.value,
    VoiceCampaignRecipientStatus.BUSY.value,
    VoiceCampaignRecipientStatus.FAILED.value,
])

# Fixed, app-specific namespace for deterministic recipient correlation ids.
# Never change this value — doing so would change every future campaign's
# correlation ids relative to past ones for no functional benefit.
_CORRELATION_NAMESPACE = uuid_lib.UUID("6f6d1e2a-6b7a-4c1a-9e3a-9b7e2c9a5b31")

# Separate fixed namespace for per-ATTEMPT execution keys (Phase 4B) — kept
# distinct from _CORRELATION_NAMESPACE above since they identify different
# things (the recipient vs. one execution attempt of it) and must never
# collide even by coincidence.
_EXECUTION_NAMESPACE = uuid_lib.UUID("9a1c1c02-6a49-4e3e-9c3a-0f6a5f9b2a10")


def execution_key(recipient_id, attempt_number: int) -> str:
    """Deterministic per-(recipient, attempt) id — Kafka's durable
    idempotency anchor for one execution attempt (see
    VoiceCampaignRecipientAttempt and app.workers.voice_campaign_worker).
    A retried attempt gets a NEW key only because attempt_number changed,
    never because a fresh random id was minted — a redelivered copy of the
    SAME attempt always resolves to the same key."""
    return str(uuid_lib.uuid5(_EXECUTION_NAMESPACE, f"{recipient_id}:{attempt_number}"))


def _correlation_id(campaign_id, phone_e164: str) -> str:
    """Deterministic per-(campaign, phone) id — the same recipient always
    derives the same id, so a future retry can recognize "this is the same
    logical recipient" without a separate lookup table."""
    return str(uuid_lib.uuid5(_CORRELATION_NAMESPACE, f"{campaign_id}:{phone_e164}"))


class VoiceCampaignService:
    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.campaigns = VoiceCampaignRepository(session, ctx)
        self.recipients = VoiceCampaignRecipientRepository(session, ctx)
        self.contact_lists = ContactListRepository(session, ctx)
        self.contacts = ContactRepository(session, ctx)
        self.templates = VoiceTemplateRepository(session, ctx)
        self.voices = AiVoiceRepository(session)
        self.resolver = SmsRecipientResolver(self.contacts, self.contact_lists)
        self.usage = TtsUsageService(session)

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    # ===================================================================== #
    # Reads
    # ===================================================================== #
    async def list_campaigns(self, *, search=None, status=None, offset=0, limit=20):
        return await self.campaigns.search(search=search, status=status, offset=offset, limit=limit)

    async def get_campaign(self, campaign_id) -> VoiceCampaign:
        c = await self.campaigns.get_by_id(campaign_id)
        if c is None:
            raise NotFoundError("Voice campaign not found")
        return c

    async def list_recipients(self, campaign_id, *, status=None, offset=0, limit=50):
        await self.get_campaign(campaign_id)  # tenant-ownership check
        return await self.recipients.list_for_campaign(
            campaign_id, status=status, offset=offset, limit=limit,
        )

    # ===================================================================== #
    # Create / edit (draft only)
    # ===================================================================== #
    async def create_campaign(self, data, *, actor_id=None, ip=None) -> VoiceCampaign:
        if self._company_id is None:
            raise ValidationError("Voice campaigns are managed within a company")
        await self._validate_draft_refs(data.contact_list_id, data.voice_template_id, data.voice_id)

        campaign = await self.campaigns.create(
            company_id=self._company_id,
            name=data.name,
            contact_list_id=data.contact_list_id,
            voice_template_id=data.voice_template_id,
            voice_id=data.voice_id,
            scheduled_at=data.scheduled_at,
            status=VoiceCampaignStatus.DRAFT.value,
            created_by=actor_id,
        )
        await self.audit.record(
            action="create", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": campaign.name},
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def update_campaign(self, campaign_id, data, *, actor_id=None, ip=None) -> VoiceCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status != VoiceCampaignStatus.DRAFT.value:
            raise ValidationError("Only draft campaigns can be edited")

        patch = data.model_dump(exclude_unset=True)
        if {"contact_list_id", "voice_template_id", "voice_id"} & patch.keys():
            await self._validate_draft_refs(
                patch.get("contact_list_id", campaign.contact_list_id),
                patch.get("voice_template_id", campaign.voice_template_id),
                patch.get("voice_id", campaign.voice_id),
            )
        if patch:
            await self.campaigns.update(campaign, **patch)
            await self.audit.record(
                action="update", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values={k: (str(v) if isinstance(v, uuid_lib.UUID) else v) for k, v in patch.items()},
            )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def delete_campaign(self, campaign_id, *, actor_id=None, ip=None) -> None:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status != VoiceCampaignStatus.DRAFT.value:
            raise ValidationError("Only draft campaigns can be deleted")
        await self.campaigns.soft_delete(campaign)
        await self.audit.record(
            action="delete", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()

    async def _validate_draft_refs(self, contact_list_id, voice_template_id, voice_id):
        """Light validation for draft create/edit — existence only. The
        FULL validation (active status, plan availability, entitlement) is
        deliberately re-run from scratch at Start time (see
        start_campaign), because a draft can sit around for a while and
        any of these could have changed since it was saved."""
        if contact_list_id is not None and await self.contact_lists.get_by_id(contact_list_id) is None:
            raise ValidationError("Contact list not found")
        if voice_template_id is not None and await self.templates.get_by_id(voice_template_id) is None:
            raise ValidationError("Voice template not found")
        if voice_id is not None:
            company = await self._load_company()
            voice = await self.voices.get_visible_to_company(
                voice_id, company_id=company.id, plan_id=company.plan_id,
            )
            if voice is None:
                raise ValidationError(
                    "Selected voice does not exist or is not available under your company's plan"
                )

    async def _load_company(self):
        company = await CompanyRepository(self.session).get_by_id(self._company_id)
        if company is None:
            raise NotFoundError("Company not found")
        return company

    async def get_usage_summary(self) -> UsageSummary:
        """Current month's TTS usage for the calling company — read-only,
        used by the campaign creation/list UI to show remaining quota."""
        company = await self._load_company()
        monthly_limit = company.plan.default_monthly_tts_characters if company.plan else None
        return await self.usage.get_summary(company_id=company.id, monthly_limit=monthly_limit)

    # ===================================================================== #
    # Pre-start estimate (draft-time, read-only, side-effect-free)
    # ===================================================================== #
    async def estimate(self, campaign_id) -> tuple[int, int, UsageSummary, list[str], bool]:
        """Returns (recipient_count, estimated_characters, usage_summary,
        errors, can_start). Never reserves quota, never touches the
        campaign row, never generates TTS — purely informational, safe to
        call as often as the Create/Edit screen wants."""
        campaign = await self.get_campaign(campaign_id)
        company = await self._load_company()
        monthly_limit = company.plan.default_monthly_tts_characters if company.plan else None

        errors: list[str] = []
        if not company.is_active:
            errors.append("Company is not active")
        if not company.ai_voice_enabled:
            errors.append("AI Voice is not enabled for this company's subscription plan")

        template = None
        if campaign.voice_template_id is None:
            errors.append("A voice template must be selected")
        else:
            template = await self.templates.get_by_id(campaign.voice_template_id)
            if template is None or template.status != VoiceTemplateStatus.ACTIVE.value:
                errors.append("Selected voice template is not active")
                template = None

        target_voice_id = campaign.voice_id or (template.voice_id if template else None)
        if target_voice_id is None:
            errors.append("A voice could not be determined from the template/override")
        else:
            voice = await self.voices.get_visible_to_company(
                target_voice_id, company_id=company.id, plan_id=company.plan_id,
            )
            if voice is None or voice.status != VoiceStatus.ACTIVE.value:
                errors.append("Selected voice is not active or not available under your company's plan")

        recipient_count = 0
        estimated_characters = 0
        if campaign.contact_list_id is None:
            errors.append("A contact list must be selected")
        else:
            contact_list = await self.contact_lists.get_by_id(campaign.contact_list_id)
            if contact_list is None:
                errors.append("Contact list not found")
            elif template is not None:
                resolved = await self.resolver.resolve(
                    source_type=SmsCampaignSource.CONTACT_LIST.value,
                    source_list_id=campaign.contact_list_id,
                )
                recipient_count = len(resolved)
                if recipient_count == 0:
                    errors.append("Contact list has no recipients with a usable mobile number")
                else:
                    for r in resolved:
                        values = build_recipient_values(
                            name=r.resolved_name, phone=r.phone_e164, company=company.name,
                        )
                        estimated_characters += len(render_template(template.text, values))

        usage_summary = await self.usage.get_summary(company_id=company.id, monthly_limit=monthly_limit)
        if (
            monthly_limit is not None
            and estimated_characters > 0
            and estimated_characters > (usage_summary.available_characters or 0)
        ):
            errors.append(
                f"Estimated {estimated_characters} characters exceeds available monthly "
                f"quota ({usage_summary.available_characters} remaining)"
            )

        can_start = (
            campaign.status == VoiceCampaignStatus.DRAFT.value
            and not errors
            and recipient_count > 0
        )
        return recipient_count, estimated_characters, usage_summary, errors, can_start

    # ===================================================================== #
    # START boundary — the atomic execution commitment point
    # ===================================================================== #
    async def start_campaign(self, campaign_id, *, actor_id=None, ip=None) -> VoiceCampaign:
        """POST /campaigns/{id}/start. Everything below runs in ONE
        transaction, committed once at the very end.

        Idempotency/atomicity contract:
          - the campaign row is locked FIRST (FOR UPDATE) — a second,
            concurrent Start request for the SAME campaign blocks here
            until the first request's transaction resolves;
          - once unblocked, it re-reads status: if the first request
            already flipped it to PROCESSING (or beyond), this call
            returns that state unchanged rather than re-doing any work —
            this is what makes "repeated Start requests" safe;
          - every validation step below can raise before anything is
            written; the quota reservation (which itself is uniqueness-
            guarded — see TtsUsageService.reserve) happens before the
            recipient rows are inserted, so a failed reservation never
            leaves an orphaned recipient snapshot behind;
          - nothing here commits except the single `await
            self.session.commit()` at the end — if anything raises before
            that line, FastAPI's get_db dependency rolls back the whole
            session on the unhandled exception, so a failed Start leaves
            the campaign exactly as DRAFT as it was before the call.
        """
        campaign = await self.campaigns.get_by_id_for_update(campaign_id)
        if campaign is None:
            raise NotFoundError("Voice campaign not found")

        if campaign.status != VoiceCampaignStatus.DRAFT.value:
            # Idempotent no-op — see docstring.
            return campaign

        # 1. Company + entitlement -------------------------------------------------
        company = await self._load_company()
        if not company.is_active:
            raise CompanyInactiveError("This company's account is not active.")
        if not company.ai_voice_enabled:
            raise CompanyInactiveError(
                "AI Voice is not enabled for this company's subscription plan."
            )

        # 2. Contact list -----------------------------------------------------------
        if campaign.contact_list_id is None:
            raise ValidationError("A contact list is required to start this campaign")
        contact_list = await self.contact_lists.get_by_id(campaign.contact_list_id)
        if contact_list is None:
            raise ValidationError("Contact list not found")

        # 3. Voice template -----------------------------------------------------------
        if campaign.voice_template_id is None:
            raise ValidationError("A voice template is required to start this campaign")
        template = await self.templates.get_by_id(campaign.voice_template_id)
        if template is None or template.status != VoiceTemplateStatus.ACTIVE.value:
            raise ValidationError("Selected voice template is not active")

        # 4. Voice: active + assigned to the company's plan -------------------------
        target_voice_id = campaign.voice_id or template.voice_id
        voice = await self.voices.get_visible_to_company(
            target_voice_id, company_id=company.id, plan_id=company.plan_id,
        )
        if voice is None or voice.status != VoiceStatus.ACTIVE.value:
            raise ValidationError(
                "Selected voice is not active or not available under your company's plan"
            )

        # 5-8. Build + render the recipient snapshot ---------------------------------
        resolved = await self.resolver.resolve(
            source_type=SmsCampaignSource.CONTACT_LIST.value,
            source_list_id=campaign.contact_list_id,
        )
        if not resolved:
            raise ValidationError("Contact list has no recipients with a usable mobile number")

        recipient_rows: list[dict] = []
        skipped: list[str] = []
        total_chars = 0
        for r in resolved:
            values = build_recipient_values(
                name=r.resolved_name, phone=r.phone_e164, company=company.name,
            )
            rendered = render_template(template.text, values)
            missing = missing_variables(template.text, values)
            if missing:
                # This recipient can't be rendered deterministically (e.g. no
                # name on file for a {{name}} template) — excluded from the
                # frozen snapshot rather than failing the whole campaign, the
                # same trade-off the SMS module makes implicitly by never
                # validating missing_variables at campaign-create time.
                skipped.append(r.phone_e164)
                continue
            char_count = len(rendered)
            total_chars += char_count
            recipient_rows.append({
                "campaign_id": campaign.id,
                "contact_id": r.contact_id,
                "phone_e164": r.phone_e164,
                "resolved_name": r.resolved_name,
                "variables": values,
                "rendered_text": rendered,
                "tts_char_count": char_count,
                "status": VoiceCampaignRecipientStatus.QUEUED.value,
                "correlation_id": _correlation_id(campaign.id, r.phone_e164),
            })

        if not recipient_rows:
            raise ValidationError(
                "No recipient could be rendered — required template variable(s) are "
                "missing for every contact in the selected list"
            )

        # 9-10. Calculate + atomically reserve TTS quota -----------------------------
        monthly_limit = company.plan.default_monthly_tts_characters if company.plan else None
        reservation = await self.usage.reserve(
            company_id=company.id, monthly_limit=monthly_limit, characters=total_chars,
            reference_type="voice_campaign", reference_id=campaign.id,
        )

        # 11. Persist the recipient snapshot -----------------------------------------
        created_recipients = await self.recipients.bulk_add(recipient_rows)

        # 12. Transition draft -> processing ------------------------------------------
        campaign.resolved_voice_id = voice.id
        campaign.reservation_id = reservation.id
        campaign.total_recipients = len(recipient_rows)
        campaign.estimated_tts_characters = total_chars
        campaign.status = VoiceCampaignStatus.PROCESSING.value
        campaign.started_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self.audit.record(
            action="start", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=company.id, ip_address=ip,
            new_values={
                "total_recipients": campaign.total_recipients,
                "estimated_tts_characters": total_chars,
                "resolved_voice_id": str(voice.id),
                "reservation_id": str(reservation.id),
                "skipped_recipients": len(skipped),
            },
        )

        # 13. Commit ------------------------------------------------------------------
        await self.session.commit()
        await self.session.refresh(campaign)

        # 14. Hand off to the Phase 4B worker ------------------------------------------
        # Deliberately AFTER the commit above: publishing is not, and cannot
        # be, part of the same atomic transaction as the DB writes (Kafka
        # and Postgres don't share a two-phase commit). If a publish fails
        # here, that recipient's row is still durably QUEUED — nothing is
        # lost — but no worker will pick it up until something re-publishes
        # for it. This is the "unavoidable external side-effect boundary"
        # called out in IMPLEMENTATION-REPORT.md: a future pass could add a
        # transactional-outbox table or a periodic "republish stuck QUEUED
        # recipients" sweep; neither exists yet. A publish failure here
        # never fails the Start request itself — the campaign is correctly
        # PROCESSING with a real, committed recipient snapshot regardless.
        for recipient in created_recipients:
            await self._publish_recipient_execution(
                company_id=company.id, campaign_id=campaign.id, recipient=recipient,
            )

        return campaign

    # ===================================================================== #
    # Cancel
    # ===================================================================== #
    async def cancel_campaign(self, campaign_id, *, actor_id=None, ip=None) -> VoiceCampaign:
        campaign = await self.campaigns.get_by_id_for_update(campaign_id)
        if campaign is None:
            raise NotFoundError("Voice campaign not found")
        if campaign.status not in VOICE_CAMPAIGN_CANCELLABLE_STATUSES:
            raise ValidationError(
                "Only draft, scheduled, or processing campaigns can be cancelled"
            )

        if campaign.reservation_id is not None:
            # Releases whatever's still outstanding on the campaign-level
            # reservation — a no-op if it's already closed (e.g. Phase 4B
            # already fully consumed it by the time a cancel request lands).
            await self.usage.release(reference_type="voice_campaign", reference_id=campaign.id)

        campaign.status = VoiceCampaignStatus.CANCELLED.value
        await self.session.flush()

        await self.audit.record(
            action="cancel", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=campaign.company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    # ===================================================================== #
    # Phase 4B — execution handoff, manual retry, aggregate rollup
    # ===================================================================== #
    async def _publish_recipient_execution(
        self, *, company_id, campaign_id, recipient: VoiceCampaignRecipient,
    ) -> None:
        """Best-effort Kafka publish for one recipient's execution attempt —
        never raises (see the call site's comment in start_campaign for why
        a publish failure must not fail the Start/retry request itself)."""
        key = execution_key(recipient.id, recipient.attempt_count)
        try:
            producer = await get_producer()
            await producer.produce(
                KafkaTopics.VOICE_CAMPAIGN_RECIPIENT_EXECUTE,
                key=str(company_id),
                value={
                    "company_id": str(company_id),
                    "campaign_id": str(campaign_id),
                    "recipient_id": str(recipient.id),
                    "attempt_number": recipient.attempt_count,
                    "execution_key": key,
                },
                # Seeds PlatformConsumer's in-memory dedup with OUR OWN
                # deterministic key instead of a random one — belt-and-
                # suspenders alongside the DB-level uniqueness on
                # VoiceCampaignRecipientAttempt.execution_key.
                message_id=key,
            )
        except Exception:  # noqa: BLE001 — publish must never break the caller
            logger.exception(
                "voice_campaign_publish_failed campaign_id=%s recipient_id=%s "
                "execution_key=%s — recipient remains queued, undelivered "
                "until something republishes for it",
                campaign_id, recipient.id, key,
            )

    async def retry_recipient(
        self, campaign_id, recipient_id, *, actor_id=None, ip=None,
    ) -> VoiceCampaignRecipient:
        """POST /{campaign_id}/recipients/{recipient_id}/retry. Only a
        recipient currently FAILED/NO_ANSWER/BUSY is retryable — never
        COMPLETED (spec: must not create another call for a success), and
        never a recipient still mid-flight (QUEUED/PROCESSING/CALLING/
        ANSWERED — there's already an attempt in progress). Bumps
        attempt_count and republishes under a brand-new execution_key, so
        this is an explicit new attempt, not a replay of the old one — the
        old attempt's VoiceCampaignRecipientAttempt row is left untouched as
        history.

        Also reopens the CAMPAIGN if finalize_if_done already rolled it up
        to COMPLETED/PARTIALLY_COMPLETED/FAILED — a terminal recipient
        failing was very possibly what finalized it in the first place, and
        the worker refuses to touch a non-PROCESSING campaign (see
        process_recipient_execution's own "campaign not processing" guard),
        so without this the retried event would just be silently skipped.
        """
        campaign = await self.campaigns.get_by_id_for_update(campaign_id)  # lock first
        if campaign is None:
            raise NotFoundError("Voice campaign not found")

        recipient = await self.recipients.try_start_retry(
            recipient_id, campaign_id=campaign.id,
            allowed_from=list(_RETRYABLE_RECIPIENT_STATUSES),
        )
        if recipient is None:
            raise ValidationError(
                "Recipient is not in a retryable state (must be failed, no answer, or busy)"
            )

        if campaign.status in (
            VoiceCampaignStatus.COMPLETED.value,
            VoiceCampaignStatus.PARTIALLY_COMPLETED.value,
            VoiceCampaignStatus.FAILED.value,
        ):
            campaign.status = VoiceCampaignStatus.PROCESSING.value
            campaign.completed_at = None
            await self.session.flush()

        await self.audit.record(
            action="recipient_retry", entity_type=_RECIPIENT_ENTITY, entity_id=recipient.id,
            actor_id=actor_id, company_id=campaign.company_id, ip_address=ip,
            new_values={"attempt_count": recipient.attempt_count},
        )
        await self.session.commit()
        await self.session.refresh(recipient)

        await self._publish_recipient_execution(
            company_id=campaign.company_id, campaign_id=campaign.id, recipient=recipient,
        )
        return recipient

    async def finalize_if_done(self, campaign_id) -> VoiceCampaign | None:
        """Concurrency-safe campaign aggregate rollup — called by the worker
        after every recipient reaches a terminal state (never by the API
        layer). Locks the campaign row first: if two workers finish the
        campaign's last two recipients at the same instant, only one of them
        actually performs the transition below; the other's status re-check
        (still PROCESSING?) fails after acquiring the lock and it exits
        having done nothing, once the first one's commit is visible.

        Returns the campaign if THIS call finalized it, or None if there's
        nothing to do (recipients still in flight, campaign not PROCESSING,
        or another worker already finalized it).
        """
        campaign = await self.campaigns.get_by_id_for_update(campaign_id)
        if campaign is None or campaign.status != VoiceCampaignStatus.PROCESSING.value:
            return None

        counts = await self.recipients.count_by_status(campaign_id)
        non_terminal = sum(
            n for status, n in counts.items() if status not in _TERMINAL_RECIPIENT_STATUSES
        )
        if non_terminal > 0:
            return None  # still in flight — not our job yet

        total = sum(counts.values())
        completed = counts.get(VoiceCampaignRecipientStatus.COMPLETED.value, 0)
        if total == 0:
            return None  # defensive — should never happen once Start has run
        if completed == total:
            campaign.status = VoiceCampaignStatus.COMPLETED.value
        elif completed > 0:
            campaign.status = VoiceCampaignStatus.PARTIALLY_COMPLETED.value
        else:
            campaign.status = VoiceCampaignStatus.FAILED.value
        campaign.completed_at = datetime.now(timezone.utc)

        if campaign.reservation_id is not None:
            # Returns whatever's left un-consumed (failed/no-answer/busy
            # recipients' share of the original estimate, plus any per-
            # recipient actual-vs-estimate slack) back to the monthly pool.
            await self.usage.release(reference_type="voice_campaign", reference_id=campaign.id)

        await self.session.flush()
        await self.audit.record(
            action="execution_finalized", entity_type=_CAMPAIGN_ENTITY, entity_id=campaign.id,
            company_id=campaign.company_id,
            new_values={"status": campaign.status, "recipient_counts": counts},
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign
