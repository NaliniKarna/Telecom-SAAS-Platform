"""Aggregates all v1 sub-routers."""
from fastapi import APIRouter

from app.api.v1.routes import audit_logs, auth, change_requests, companies, company_settings, group, api_key, contact, contact_list, subscription_plans, dashboard, platform_settings, sms, sms_campaign, sms_analytics, users

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
