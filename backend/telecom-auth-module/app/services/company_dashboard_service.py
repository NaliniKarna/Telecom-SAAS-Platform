"""Company dashboard service (Company Admin, self-scoped, read-only).

Aggregates KPIs and feeds for one company. The company_id is supplied by the
route from the authenticated token — never from client input — so every query
is confined to the caller's own tenant.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CallbackOutcome, MissedCallStatus, SmsMessageStatus, UserStatus
from app.core.exceptions import NotFoundError
from app.models.api_key import ApiKey
from app.models.company import Company
from app.models.contact import Contact, ContactList
from app.models.group import Group
from app.models.missed_call import MissedCall, MissedCallCallback
from app.models.sms import SmsCampaign, SmsMessage, SmsSenderId, SmsTemplate
from app.models.user import User
from app.schemas.company_dashboard import (
    CompanyDashboardOverview,
    CompanyKpis,
    CompanySummary,
    RecentCompanyUser,
)


class CompanyDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def overview(
        self, company_id, *, recent_limit: int = 5
    ) -> CompanyDashboardOverview:
        if company_id is None:
            raise NotFoundError("No company associated with this account")
        company = await self.session.get(Company, company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Company not found")

        total_users, active_users = await self._user_counts(company_id)
        sms_counts = await self._sms_counts(company_id)
        mc_kpis = await self._missed_call_kpis(company_id)
        kpis = CompanyKpis(
            total_users=total_users,
            active_users=active_users,
            total_groups=await self._count(Group, company_id),
            total_api_keys=await self._count(ApiKey, company_id, soft_delete=False),
            total_contacts=await self._count(Contact, company_id),
            total_contact_lists=await self._count(ContactList, company_id),
            total_sms_campaigns=sms_counts["campaigns"],
            total_sms_templates=sms_counts["templates"],
            total_sms_sender_ids=sms_counts["sender_ids"],
            total_sms_messages=sms_counts["messages"],
            messages_sent_today=await self._messages_sent_today(company_id),
            delivery_rate=await self._delivery_rate(company_id),
            **mc_kpis,
        )
        summary = CompanySummary(
            company_name=company.name,
            plan_name=company.plan.name if company.plan else None,
            plan_status=(
                company.status.value
                if hasattr(company.status, "value")
                else str(company.status)
            ),
            user_limit=company.max_users,
            current_user_count=total_users,
        )
        return CompanyDashboardOverview(
            kpis=kpis,
            summary=summary,
            recent_created_users=await self._recent_users(
                company_id, recent_limit, by="created_at"
            ),
            recent_updated_users=await self._recent_users(
                company_id, recent_limit, by="updated_at"
            ),
        )

    async def _count(self, model, company_id, *, soft_delete: bool = True) -> int:
        stmt = select(func.count(model.id)).where(model.company_id == company_id)
        if soft_delete and hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))
        return int(await self.session.scalar(stmt) or 0)

    async def _messages_sent_today(self, company_id) -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(await self.session.scalar(
            select(func.count(SmsMessage.id)).where(
                SmsMessage.company_id == company_id,
                SmsMessage.sent_at >= start,
            )
        ) or 0)

    async def _delivery_rate(self, company_id) -> float:
        rows = (await self.session.execute(
            select(SmsMessage.status, func.count())
            .where(SmsMessage.company_id == company_id)
            .group_by(SmsMessage.status)
        )).all()
        counts = {str(s): int(n) for s, n in rows}
        delivered = counts.get(SmsMessageStatus.DELIVERED.value, 0)
        attempted = (delivered
                     + counts.get(SmsMessageStatus.FAILED.value, 0)
                     + counts.get(SmsMessageStatus.SENT.value, 0))
        return round(delivered / attempted * 100, 2) if attempted else 0.0

    async def _user_counts(self, company_id) -> tuple[int, int]:
        rows = (await self.session.execute(
            select(User.status, func.count())
            .where(User.company_id == company_id, User.deleted_at.is_(None))
            .group_by(User.status)
        )).all()
        by_status = {s: int(n) for s, n in rows}
        total = sum(by_status.values())
        active = int(
            by_status.get(UserStatus.ACTIVE)
            or by_status.get(UserStatus.ACTIVE.value)
            or 0
        )
        return total, active

    async def _sms_counts(self, company_id) -> dict[str, int]:
        campaigns = await self.session.scalar(
            select(func.count(SmsCampaign.id)).where(
                SmsCampaign.company_id == company_id,
                SmsCampaign.deleted_at.is_(None),
            )
        )
        templates = await self.session.scalar(
            select(func.count(SmsTemplate.id)).where(
                SmsTemplate.company_id == company_id,
                SmsTemplate.deleted_at.is_(None),
            )
        )
        sender_ids = await self.session.scalar(
            select(func.count(SmsSenderId.id)).where(
                SmsSenderId.company_id == company_id,
                SmsSenderId.deleted_at.is_(None),
            )
        )
        messages = await self.session.scalar(
            select(func.count(SmsMessage.id)).where(
                SmsMessage.company_id == company_id,
            )
        )
        return {
            "campaigns": int(campaigns or 0),
            "templates": int(templates or 0),
            "sender_ids": int(sender_ids or 0),
            "messages": int(messages or 0),
        }

    async def _missed_call_kpis(self, company_id) -> dict:
        """Compute missed-call KPIs for the company dashboard."""
        # Missed calls today
        start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today = int(await self.session.scalar(
            select(func.count(MissedCall.id)).where(
                MissedCall.company_id == company_id,
                MissedCall.received_at >= start,
            )
        ) or 0)

        # Pending (new + acknowledged)
        pending = int(await self.session.scalar(
            select(func.count(MissedCall.id)).where(
                MissedCall.company_id == company_id,
                MissedCall.status.in_([
                    MissedCallStatus.NEW.value,
                    MissedCallStatus.ACKNOWLEDGED.value,
                ]),
            )
        ) or 0)

        # Callback success rate
        cb_row = (await self.session.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case(
                        (MissedCallCallback.outcome == CallbackOutcome.ANSWERED.value, 1),
                        else_=0,
                    )
                ).label("answered"),
            ).where(MissedCallCallback.company_id == company_id)
        )).one()
        cb_total = int(cb_row.total or 0)
        cb_answered = int(cb_row.answered or 0)
        success_rate = round(cb_answered / cb_total * 100, 1) if cb_total else 0.0

        return {
            "missed_calls_today": today,
            "pending_callbacks": pending,
            "callback_success_rate": success_rate,
        }

    async def _recent_users(
        self, company_id, limit: int, *, by: str
    ) -> list[RecentCompanyUser]:
        col = getattr(User, by)
        rows = (await self.session.execute(
            select(User)
            .where(User.company_id == company_id, User.deleted_at.is_(None))
            .order_by(col.desc())
            .limit(limit)
        )).scalars().all()
        out: list[RecentCompanyUser] = []
        for u in rows:
            item = RecentCompanyUser.model_validate(u)
            item.full_name = (
                " ".join(filter(None, [u.first_name, u.last_name])) or None
            )
            item.status = (
                u.status.value if hasattr(u.status, "value") else str(u.status)
            )
            out.append(item)
        return out
