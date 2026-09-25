"""TTS Usage Metering service — the quota engine behind spec section 1.

NOT a billing system: no invoices, no charges, no payment integration. This
is purely "how many TTS characters has this company used this calendar
month, and how many more can it use" — a ceiling check plus a reserve/
consume/release state machine so a Voice Campaign's estimated cost is
locked in atomically at Start, without permanently charging the whole
estimate before any TTS has actually been generated (that's Phase 4B's
job, per the spec's reservation model).

State machine per reservation (see TtsUsageReservation):

    reserve()  -> creates an OPEN reservation, adds reserved_characters to
                  the month's TtsUsage.reserved_characters. Idempotent: a
                  second reserve() call with the same (reference_type,
                  reference_id) returns the existing reservation unchanged
                  — it never reserves twice for the same logical action.

    consume()  -> converts some/all of an OPEN reservation's *remaining*
                  characters (reserved_characters - consumed_characters)
                  into real TtsUsage.consumed_characters. Partial-safe: can
                  be called more than once against the same reservation
                  (e.g. Phase 4B consuming per-recipient against one
                  campaign-level reservation) as long as the running total
                  never exceeds what was reserved. Once fully consumed the
                  reservation closes. A no-op (returns the reservation
                  as-is) if it's already closed — safe to retry.

    release()  -> returns whatever's still outstanding (reserved minus
                  already-consumed) back to the pool and closes the
                  reservation. A no-op if already closed — safe to retry,
                  and safe to call after a partial consume() (only the
                  genuinely-unused remainder is released, matching the
                  spec's "partial campaign completion leaves only
                  genuinely consumed characters charged").

Lock ordering: every method locks the TtsUsage row before the
TtsUsageReservation row (see app.repositories.tts_usage_repository module
docstring) — this is what lets reserve() and consume()/release() run
concurrently against the same company+month without deadlocking each
other; it must not be reversed by future callers.

Quota rule (spec section 1): NULL monthly_limit = unlimited (never
blocks); 0 = no TTS usage allowed at all (any reserve() with
characters > 0 is rejected); a positive value is a hard ceiling on
consumed + reserved for the month.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.voice_campaign import TtsUsage, TtsUsageReservation
from app.repositories.tts_usage_repository import (
    TtsUsageRepository,
    TtsUsageReservationRepository,
)


def current_usage_month(when: datetime | None = None) -> date:
    """The calendar month key used everywhere in this module — always the
    first day of the month, UTC. Monthly separation is just "a different
    row" (see TtsUsage's unique constraint); nothing resets on a timer."""
    moment = when or datetime.now(timezone.utc)
    return moment.date().replace(day=1)


@dataclass
class UsageSummary:
    usage_month: date
    monthly_limit: int | None
    consumed_characters: int
    reserved_characters: int
    available_characters: int | None  # None means unlimited


class TtsUsageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.usage = TtsUsageRepository(session)
        self.reservations = TtsUsageReservationRepository(session)

    # --- reads --------------------------------------------------------------
    async def get_summary(
        self, *, company_id, monthly_limit: int | None, when: datetime | None = None,
    ) -> UsageSummary:
        month = current_usage_month(when)
        row = await self.usage.get_readonly(company_id, month)
        consumed = row.consumed_characters if row else 0
        reserved = row.reserved_characters if row else 0
        available = (
            None if monthly_limit is None else max(0, monthly_limit - consumed - reserved)
        )
        return UsageSummary(
            usage_month=month, monthly_limit=monthly_limit,
            consumed_characters=consumed, reserved_characters=reserved,
            available_characters=available,
        )

    # --- reserve --------------------------------------------------------------
    async def reserve(
        self, *, company_id, monthly_limit: int | None, characters: int,
        reference_type: str, reference_id, when: datetime | None = None,
    ) -> TtsUsageReservation:
        """Atomically check-and-reserve `characters` against the company's
        monthly ceiling. Raises ValidationError (422) if the request would
        exceed the ceiling. Idempotent per (reference_type, reference_id) —
        see module docstring."""
        if characters < 0:
            raise ValidationError("Cannot reserve a negative character count")

        month = current_usage_month(when)

        # Idempotency fast path: already reserved for this exact reference —
        # return it unchanged rather than reserving again. This is the
        # primary defense against duplicate Start requests; the DB unique
        # constraint (caught below) is the backstop for the race where two
        # requests both miss this check at the same instant.
        existing = await self.reservations.get_by_reference(reference_type, reference_id)
        if existing is not None:
            return existing

        usage = await self.usage.get_for_update(company_id, month)  # lock usage FIRST

        if monthly_limit is not None:
            available = monthly_limit - usage.consumed_characters - usage.reserved_characters
            if characters > available:
                raise ValidationError(
                    f"Insufficient TTS quota: requested {characters} characters, "
                    f"only {max(available, 0)} available this month"
                )
        # monthly_limit is None -> unlimited, always allowed regardless of characters.

        # The reservation INSERT is attempted BEFORE touching usage's
        # counters, deliberately: holding the usage row's FOR UPDATE lock
        # already fully serializes concurrent reserve() calls for the same
        # company+month (a second caller blocks until the first commits or
        # rolls back), so in practice this IntegrityError path is a
        # defense-in-depth backstop, not the primary safeguard — but because
        # it's wrapped in its own SAVEPOINT (begin_nested), hitting it never
        # rolls back the caller's outer transaction (e.g. a campaign row
        # already staged in this same session/request), only the failed
        # INSERT itself.
        try:
            async with self.session.begin_nested():
                reservation = await self.reservations.create(
                    company_id=company_id, usage_month=month,
                    reference_type=reference_type, reference_id=reference_id,
                    reserved_characters=characters,
                )
        except IntegrityError:
            existing = await self.reservations.get_by_reference(reference_type, reference_id)
            if existing is None:
                raise  # genuinely unexpected — surface the original error
            return existing

        usage.reserved_characters += characters
        usage.request_count += 1
        await self.session.flush()
        return reservation

    # --- consume / release ---------------------------------------------------
    async def consume(
        self, *, reference_type: str, reference_id, characters: int | None = None,
    ) -> TtsUsageReservation | None:
        """Convert up to `characters` (default: everything still
        outstanding) of this reservation into real usage. No-op if the
        reservation doesn't exist or is already closed."""
        pointer = await self.reservations.get_by_reference(reference_type, reference_id)
        if pointer is None:
            return None

        # Lock usage BEFORE the reservation row (see module docstring).
        usage = await self.usage.get_for_update(pointer.company_id, pointer.usage_month)
        reservation = await self.reservations.get_by_reference(
            reference_type, reference_id, for_update=True,
        )
        if reservation is None or reservation.status == "closed":
            return reservation

        remaining = reservation.reserved_characters - reservation.consumed_characters
        amount = remaining if characters is None else max(0, min(characters, remaining))
        if amount <= 0:
            return reservation

        usage.reserved_characters -= amount
        usage.consumed_characters += amount
        reservation.consumed_characters += amount
        if reservation.consumed_characters >= reservation.reserved_characters:
            reservation.status = "closed"

        await self.session.flush()
        return reservation

    async def release(
        self, *, reference_type: str, reference_id,
    ) -> TtsUsageReservation | None:
        """Return whatever's still outstanding on this reservation to the
        pool and close it. No-op if already closed (safe to call twice —
        e.g. once from a failure handler and again from cleanup)."""
        pointer = await self.reservations.get_by_reference(reference_type, reference_id)
        if pointer is None:
            return None

        usage = await self.usage.get_for_update(pointer.company_id, pointer.usage_month)
        reservation = await self.reservations.get_by_reference(
            reference_type, reference_id, for_update=True,
        )
        if reservation is None or reservation.status == "closed":
            return reservation

        remaining = reservation.reserved_characters - reservation.consumed_characters
        if remaining > 0:
            usage.reserved_characters -= remaining
        reservation.status = "closed"

        await self.session.flush()
        return reservation
