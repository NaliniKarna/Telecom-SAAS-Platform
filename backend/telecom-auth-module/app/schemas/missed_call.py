"""Missed Call Platform Pydantic schemas (Phase 6).

Schema layers:
  - MissedCall*       : CRUD + status/assignment patches
  - MissedCallNote*   : append-only note reads / creates
  - MissedCallCallback* : callback attempt reads / creates / outcome patches
  - MissedCallDashboard : overview stats for the missed-call dashboard
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Missed Calls ─────────────────────────────────────────────────────────────

class MissedCallCreate(BaseModel):
    """Register a new missed call (from AMI event or manual API entry)."""
    caller_number: str = Field(min_length=1, max_length=80)
    called_number: str = Field(min_length=1, max_length=80)
    called_extension_id: Optional[uuid.UUID] = None
    received_at: datetime
    ring_duration_seconds: Optional[int] = None
    source_call_id: Optional[uuid.UUID] = None
    caller_name: Optional[str] = Field(default=None, max_length=255)


class MissedCallStatusPatch(BaseModel):
    status: Annotated[
        str, Field(pattern="^(new|acknowledged|returned|closed)$")
    ]


class MissedCallAssignPatch(BaseModel):
    assigned_to: Optional[uuid.UUID] = None  # None = unassign


class MissedCallNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    missed_call_id: uuid.UUID
    author_id: uuid.UUID
    author_name: Optional[str] = None
    body: str
    created_at: datetime

    @classmethod
    def from_model(cls, m) -> "MissedCallNoteRead":
        name = None
        if m.author:
            name = f"{m.author.first_name} {m.author.last_name}".strip() or m.author.email
        return cls(
            id=m.id,
            missed_call_id=m.missed_call_id,
            author_id=m.author_id,
            author_name=name,
            body=m.body,
            created_at=m.created_at,
        )


class MissedCallNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MissedCallCallbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    missed_call_id: uuid.UUID
    performed_by: uuid.UUID
    performer_name: Optional[str] = None
    extension_id: Optional[uuid.UUID]
    extension_number: Optional[str] = None
    voice_call_id: Optional[uuid.UUID]
    outcome: Optional[str]
    duration_seconds: Optional[int]
    notes: Optional[str]
    attempted_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, m) -> "MissedCallCallbackRead":
        name = None
        if m.performer:
            name = f"{m.performer.first_name} {m.performer.last_name}".strip() or m.performer.email
        return cls(
            id=m.id,
            missed_call_id=m.missed_call_id,
            performed_by=m.performed_by,
            performer_name=name,
            extension_id=m.extension_id,
            extension_number=m.extension.extension_number if m.extension else None,
            voice_call_id=m.voice_call_id,
            outcome=m.outcome,
            duration_seconds=m.duration_seconds,
            notes=m.notes,
            attempted_at=m.attempted_at,
            created_at=m.created_at,
        )


class CallbackRequest(BaseModel):
    """Initiate a callback via the Voice Platform dialer."""
    extension_id: Optional[uuid.UUID] = None
    caller_number: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = Field(default=None, max_length=4000)


class CallbackOutcomePatch(BaseModel):
    outcome: Annotated[
        str, Field(pattern="^(answered|no_answer|busy|voicemail|failed)$")
    ]
    duration_seconds: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class MissedCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    caller_number: str
    called_number: str
    called_extension_id: Optional[uuid.UUID]
    called_extension_number: Optional[str] = None
    status: str
    received_at: datetime
    ring_duration_seconds: Optional[int]
    source_call_id: Optional[uuid.UUID]
    assigned_to: Optional[uuid.UUID]
    assignee_name: Optional[str] = None
    callback_count: int
    caller_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m) -> "MissedCallRead":
        assignee = None
        if m.assignee:
            assignee = f"{m.assignee.first_name} {m.assignee.last_name}".strip() or m.assignee.email
        return cls(
            id=m.id,
            company_id=m.company_id,
            caller_number=m.caller_number,
            called_number=m.called_number,
            called_extension_id=m.called_extension_id,
            called_extension_number=(
                m.called_extension.extension_number if m.called_extension else None
            ),
            status=m.status,
            received_at=m.received_at,
            ring_duration_seconds=m.ring_duration_seconds,
            source_call_id=m.source_call_id,
            assigned_to=m.assigned_to,
            assignee_name=assignee,
            callback_count=m.callback_count,
            caller_name=m.caller_name,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class MissedCallDetail(MissedCallRead):
    """Full missed call with notes and callback history."""
    notes: list[MissedCallNoteRead] = []
    callbacks: list[MissedCallCallbackRead] = []

    @classmethod
    def from_model_full(cls, m) -> "MissedCallDetail":
        base = MissedCallRead.from_model(m)
        return cls(
            **base.model_dump(),
            notes=[MissedCallNoteRead.from_model(n) for n in (m.notes or [])],
            callbacks=[MissedCallCallbackRead.from_model(c) for c in (m.callbacks or [])],
        )


class PaginatedMissedCalls(BaseModel):
    items: list[MissedCallRead]
    total: int
    offset: int
    limit: int


# ── Dashboard ────────────────────────────────────────────────────────────────

class MissedCallDashboardStats(BaseModel):
    """High-level missed call summary for the company dashboard."""
    missed_today: int
    pending_callbacks: int             # status in (new, acknowledged)
    total_callbacks: int
    callbacks_answered: int
    callback_success_rate_pct: float   # 0-100
    avg_callback_time_seconds: float   # average time from received_at to first callback
    total_missed: int
    by_status: dict[str, int]          # { "new": 5, "acknowledged": 3, ... }
