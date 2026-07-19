"""Company dashboard DTOs (Company Admin, self-scoped, read-only)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyKpis(BaseModel):
    total_users: int
    active_users: int
    total_groups: int = 0
    total_api_keys: int = 0
    total_contacts: int = 0
    total_contact_lists: int = 0
    total_sms_campaigns: int = 0
    total_sms_templates: int = 0
    total_sms_sender_ids: int = 0
    total_sms_messages: int = 0
    messages_sent_today: int = 0
    delivery_rate: float = 0.0
    # ── Missed Call KPIs (Phase 6) ──
    missed_calls_today: int = 0
    pending_callbacks: int = 0
    callback_success_rate: float = 0.0


class CompanySummary(BaseModel):
    company_name: str
    plan_name: str | None = None
    plan_status: str
    user_limit: int | None = None
    current_user_count: int


class RecentCompanyUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CompanyDashboardOverview(BaseModel):
    kpis: CompanyKpis
    summary: CompanySummary
    recent_created_users: list[RecentCompanyUser]
    recent_updated_users: list[RecentCompanyUser]
