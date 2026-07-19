"""Company self-registration + approval tests.

Verifies the flow contract with the DB/repo seams stubbed: registration creates
a PENDING_APPROVAL company + PENDING company_admin (unverified) and issues a
verification token; approval is blocked until the admin verifies email, then
flips company + admin to ACTIVE; rejection sets REJECTED. A final regression
test confirms the *existing* login gate blocks a pending_approval company — the
enforcement this whole feature relies on.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.constants import CompanyStatus, UserStatus
from app.core.exceptions import ConflictError, ValidationError
from app.schemas.registration import CompanyRegistrationRequest
from app.services.registration_service import RegistrationService


def _now():
    return datetime.now(timezone.utc)


class FakeSession:
    def __init__(self):
        self._store = {}

    def put(self, obj):
        self._store[str(obj.id)] = obj

    async def get(self, _model, pk):
        return self._store.get(str(pk))

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


class FakeCompanyRepo:
    def __init__(self):
        self.created = None

    async def slug_exists(self, slug, exclude_id=None):
        return False

    async def create(self, **kw):
        self.created = SimpleNamespace(
            id=uuid.uuid4(), created_at=_now(), deleted_at=None,
            metadata_=kw.get("metadata_") or {}, **{k: v for k, v in kw.items() if k != "metadata_"},
        )
        return self.created


class FakeUserRepo:
    def __init__(self):
        self.created = None
        self.role_set = False

    async def get_role(self, name):
        return SimpleNamespace(name=name)

    async def email_exists(self, email):
        return False

    async def create(self, **kw):
        self.created = SimpleNamespace(
            id=uuid.uuid4(), created_at=_now(), deleted_at=None,
            full_name=kw.get("first_name") or kw.get("email"), **kw,
        )
        return self.created

    async def set_role(self, user, role, *, assigned_by=None):
        self.role_set = True

    async def get_by_id_unscoped(self, uid):
        return self.created if self.created and str(self.created.id) == str(uid) else None


class FakeAudit:
    async def record(self, **kw):
        return None


def _service():
    session = FakeSession()
    svc = RegistrationService(
        session, company_repo=FakeCompanyRepo(), user_repo=FakeUserRepo(),
        audit=FakeAudit(),
    )
    return svc, session


def _payload(**over):
    base = dict(
        company_name="Acme Comms", admin_first_name="Asha", admin_last_name="Rai",
        admin_email="asha@acme.com", password="s3curepass99", contact_phone="+9779800000000",
    )
    base.update(over)
    return CompanyRegistrationRequest(**base)


@pytest.mark.asyncio
async def test_register_creates_pending_company_and_admin_with_token():
    svc, _ = _service()
    company, user, token = await svc.register_company(_payload())

    assert company.status == CompanyStatus.PENDING_APPROVAL
    assert user.status == UserStatus.PENDING
    assert user.is_email_verified is False
    assert svc.users.role_set is True                    # company_admin assigned
    assert company.metadata_["admin_user_id"] == str(user.id)
    assert isinstance(token, str) and len(token) > 20    # verification token issued


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email():
    svc, _ = _service()

    async def exists(email):
        return True

    svc.users.email_exists = exists
    with pytest.raises(ConflictError):
        await svc.register_company(_payload())


@pytest.mark.asyncio
async def test_approve_blocked_until_email_verified():
    svc, session = _service()
    company, user, _ = await svc.register_company(_payload())
    session.put(company)                 # so session.get finds it
    # admin still unverified
    with pytest.raises(ValidationError):
        await svc.approve(company.id, reviewer_id=uuid.uuid4())
    assert company.status == CompanyStatus.PENDING_APPROVAL


@pytest.mark.asyncio
async def test_approve_activates_company_and_admin_when_verified():
    svc, session = _service()
    company, user, _ = await svc.register_company(_payload())
    session.put(company)
    user.is_email_verified = True        # email verified via existing flow

    result = await svc.approve(company.id, reviewer_id=uuid.uuid4())
    assert result.status == CompanyStatus.ACTIVE
    assert user.status == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_reject_sets_rejected_status_with_reason():
    svc, session = _service()
    company, _user, _ = await svc.register_company(_payload())
    session.put(company)

    result = await svc.reject(company.id, reviewer_id=uuid.uuid4(), reason="Incomplete details")
    assert result.status == CompanyStatus.REJECTED
    assert result.metadata_["rejection_reason"] == "Incomplete details"


def test_login_gate_blocks_pending_approval_company():
    """Regression: the existing login gate is what enforces 'only approved
    companies can access' — a pending_approval company must block login even if
    the user row were active."""
    from app.core.exceptions import InactiveAccountError
    from app.services.auth_service import AuthService

    user = SimpleNamespace(
        status=UserStatus.ACTIVE,
        company=SimpleNamespace(status=CompanyStatus.PENDING_APPROVAL),
    )
    with pytest.raises(InactiveAccountError):
        # _assert_login_allowed only reads `user`; a dummy self is fine.
        AuthService._assert_login_allowed(object(), user)
