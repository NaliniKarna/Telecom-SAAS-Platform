"""External API — programmatic SMS sending.

This is the ONLY endpoint in the application that accepts `X-API-Key`
authentication. It deliberately does not sit alongside the Company Admin
`/sms/*` routes: those all take `CurrentUser`/`CurrentContext` (JWT), and
nothing here does. `CurrentApiKey` and `CurrentUser` are two independent
dependency chains (see app.api.v1.deps) — a JWT cannot authenticate here,
and an API key cannot authenticate against any JWT-protected route.

No SMS-sending logic lives in this file. It validates the request shape,
confirms the key's company is active, and hands off entirely to
ExternalSmsService, which drives the same SmsCampaignService the console
uses (see that module's docstring for why).
"""
from fastapi import APIRouter, Request, status

from app.api.v1.deps import CurrentApiKey, DbSession
from app.core.http import client_ip
from app.schemas.external_sms import ExternalSmsSendRequest, ExternalSmsSendResponse
from app.services.external_sms_service import ExternalSmsService

router = APIRouter(prefix="/external/sms", tags=["External API"])


@router.post(
    "/send",
    response_model=ExternalSmsSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_external_sms(
    payload: ExternalSmsSendRequest,
    request: Request,
    key_ctx: CurrentApiKey,
    db: DbSession,
) -> ExternalSmsSendResponse:
    service = ExternalSmsService(db, key_ctx.company_id)
    await service.assert_company_active()
    result = await service.send(payload, client_ip=client_ip(request))
    return ExternalSmsSendResponse(
        campaign_id=result.campaign_id,
        contact_id=result.contact_id,
        status=result.status,
    )