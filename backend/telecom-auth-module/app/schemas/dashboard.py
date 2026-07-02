"""Dashboard / platform-overview DTOs (read-only aggregates)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardKpis(BaseModel):
    total_companies: int
    active_companies: int
    suspended_companies: int
    deactivated_companies: int
    total_plans: int


class RecentCompany(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: str
    plan_name: str | None = None
    created_at: datetime


class RecentActivity(BaseModel):
    id: int
    action: str
    entity_type: str
    actor_name: str | None = None
    company_name: str | None = None
    created_at: datetime


class PlanDistribution(BaseModel):
    plan_id: uuid.UUID | None = None
    plan_name: str
    company_count: int


class DashboardOverview(BaseModel):
    kpis: DashboardKpis
    recent_companies: list[RecentCompany]
    recent_activity: list[RecentActivity]
    plan_distribution: list[PlanDistribution]
