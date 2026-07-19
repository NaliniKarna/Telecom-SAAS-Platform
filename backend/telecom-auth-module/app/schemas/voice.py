"""Voice Platform Pydantic schemas (Phase 5).

Schema layers:
  - VoiceExtension*  : extension CRUD + agent-status patch.
  - VoiceCallLog*    : CDR reads + originate request + status-patch.
  - VoiceAnalytics*  : overview stats + timeseries points.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Extensions ────────────────────────────────────────────────────────────────

class VoiceExtensionBase(BaseModel):
    extension_number: str = Field(min_length=1, max_length=20)
    display_name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    context: str = Field(default="from-internal", max_length=100)
    technology: str = Field(default="PJSIP", max_length=20)
    enabled: bool = True


class VoiceExtensionCreate(VoiceExtensionBase):
    user_id: Optional[uuid.UUID] = None


class VoiceExtensionUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    context: Optional[str] = Field(default=None, max_length=100)
    technology: Optional[str] = Field(default=None, max_length=20)
    enabled: Optional[bool] = None
    user_id: Optional[uuid.UUID] = None


class AgentStatusPatch(BaseModel):
    """Slim payload for agent-status updates (presence)."""
    agent_status: Annotated[str, Field(pattern="^(available|busy|away|offline)$")]


class VoiceExtensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    extension_number: str
    display_name: str
    description: Optional[str]
    context: str
    technology: str
    enabled: bool
    user_id: Optional[uuid.UUID]
    agent_status: str
    last_seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Denormalized user fields for convenience in the UI.
    assigned_user_name: Optional[str] = None
    assigned_user_email: Optional[str] = None

    @classmethod
    def from_model(cls, m) -> "VoiceExtensionRead":
        name = email = None
        if m.user:
            name = f"{m.user.first_name} {m.user.last_name}".strip() or None
            email = m.user.email
        return cls(
            id=m.id,
            company_id=m.company_id,
            extension_number=m.extension_number,
            display_name=m.display_name,
            description=m.description,
            context=m.context,
            technology=m.technology,
            enabled=m.enabled,
            user_id=m.user_id,
            agent_status=m.agent_status,
            last_seen_at=m.last_seen_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
            assigned_user_name=name,
            assigned_user_email=email,
        )


# ── Call Logs (CDR) ──────────────────────────────────────────────────────────

class OriginateRequest(BaseModel):
    """Initiate an outbound voice call (click-to-call or manual dialer)."""
    # The A-leg: the extension that will ring first (agent's handset).
    # If omitted, caller_number must be supplied instead.
    caller_extension_id: Optional[uuid.UUID] = None
    # Explicit caller number (used when no extension is selected, e.g. trunk).
    caller_number: Optional[str] = Field(default=None, max_length=80)
    # The B-leg: the number to dial.
    destination_number: str = Field(min_length=1, max_length=80)
    # Optional caller-ID override presented to the B-leg.
    caller_id_override: Optional[str] = Field(default=None, max_length=80)


class CallStatusPatch(BaseModel):
    """Update a call's status (simulation hook / manual override)."""
    status: Annotated[
        str,
        Field(
            pattern="^(initiated|ringing|answered|busy|no_answer|failed|cancelled|completed)$"
        ),
    ]
    hangup_cause: Optional[str] = Field(default=None, max_length=100)


class VoiceCallLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    connection_id: Optional[uuid.UUID]
    direction: str
    status: str
    caller_number: str
    callee_number: str
    caller_extension_id: Optional[uuid.UUID]
    callee_extension_id: Optional[uuid.UUID]
    started_at: datetime
    answered_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    ring_duration_seconds: Optional[int]
    action_id: Optional[str]
    hangup_cause: Optional[str]
    recording_url: Optional[str]
    initiated_by: Optional[uuid.UUID]
    created_at: datetime

    # Denormalized extension labels for the UI.
    caller_extension_number: Optional[str] = None
    callee_extension_number: Optional[str] = None
    initiator_name: Optional[str] = None

    @classmethod
    def from_model(cls, m) -> "VoiceCallLogRead":
        init_name = None
        if m.initiator:
            init_name = (
                f"{m.initiator.first_name} {m.initiator.last_name}".strip()
                or m.initiator.email
            )
        return cls(
            id=m.id,
            company_id=m.company_id,
            connection_id=m.connection_id,
            direction=m.direction,
            status=m.status,
            caller_number=m.caller_number,
            callee_number=m.callee_number,
            caller_extension_id=m.caller_extension_id,
            callee_extension_id=m.callee_extension_id,
            started_at=m.started_at,
            answered_at=m.answered_at,
            ended_at=m.ended_at,
            duration_seconds=m.duration_seconds,
            ring_duration_seconds=m.ring_duration_seconds,
            action_id=m.action_id,
            hangup_cause=m.hangup_cause,
            recording_url=m.recording_url,
            initiated_by=m.initiated_by,
            created_at=m.created_at,
            caller_extension_number=(
                m.caller_extension.extension_number if m.caller_extension else None
            ),
            callee_extension_number=(
                m.callee_extension.extension_number if m.callee_extension else None
            ),
            initiator_name=init_name,
        )


class PaginatedCallLogs(BaseModel):
    items: list[VoiceCallLogRead]
    total: int
    offset: int
    limit: int


# ── Analytics ────────────────────────────────────────────────────────────────

class VoiceOverviewStats(BaseModel):
    """High-level voice summary for the dashboard."""
    total_calls: int
    answered_calls: int
    answer_rate_pct: float          # 0-100
    avg_duration_seconds: float
    total_duration_seconds: int
    active_calls: int               # currently in progress
    outbound_calls: int
    inbound_calls: int
    failed_calls: int


class TimeseriesPoint(BaseModel):
    date: str                       # ISO date string, e.g. "2025-01-15"
    total: int
    answered: int
    failed: int


class VoiceTimeseriesStats(BaseModel):
    points: list[TimeseriesPoint]
    period_days: int


class ExtensionStatusSummary(BaseModel):
    """Count of extensions by agent_status for the dashboard status panel."""
    available: int
    busy: int
    away: int
    offline: int
    total: int
