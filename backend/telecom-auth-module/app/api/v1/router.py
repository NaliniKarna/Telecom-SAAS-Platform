"""Aggregates all v1 sub-routers."""
from fastapi import APIRouter

from app.api.v1.routes import (
    audit_logs,
    auth,
    ai_voice,
    admin_ai_voice,
    change_requests,
    companies,
    company_settings,
    group,
    api_key,
    contact,
    contact_list,
    dashboard,
    external_sms,
    missed_call,
    platform_settings,
    registration,
    sms,
    sms_analytics,
    sms_campaign,
    subscription_plans,
    telephony,
    users,
    voice,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(subscription_plans.router)
api_router.include_router(audit_logs.router)
api_router.include_router(dashboard.router)
api_router.include_router(platform_settings.router)
api_router.include_router(sms.router)
api_router.include_router(sms_campaign.router)
api_router.include_router(sms_analytics.router)
api_router.include_router(users.router)
api_router.include_router(company_settings.router)
api_router.include_router(change_requests.router)
api_router.include_router(group.router)
api_router.include_router(api_key.router)
api_router.include_router(contact.router)
api_router.include_router(contact_list.router)
api_router.include_router(telephony.router)
api_router.include_router(voice.router)
api_router.include_router(missed_call.router)
api_router.include_router(registration.router)
api_router.include_router(external_sms.router)
api_router.include_router(ai_voice.router)
api_router.include_router(admin_ai_voice.router)
