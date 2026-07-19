"""Telephony integration-layer tests (Phase 3).

Covers the abstraction seam and the hybrid resolution/service contract without a
live PBX: provider factory + NullAsteriskProvider, at-rest secret encryption,
the repository's hybrid resolve_effective rule, and the service's status/probe
and platform-default guard.
"""
from types import SimpleNamespace

import pytest

from app.core.constants import TelephonyConnectionStatus, TelephonyProvider
from app.core.crypto import decrypt_secret, encrypt_secret
from app.services.asterisk_provider import (
    AmiAsteriskProvider,
    ConnectionParams,
    NullAsteriskProvider,
    get_asterisk_provider,
    reset_asterisk_provider,
)


# --------------------------------------------------------------------------- #
# Provider abstraction + factory
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_null_provider_reports_connected_when_params_complete():
    provider = NullAsteriskProvider()
    status = await provider.get_status(
        ConnectionParams(host="pbx.local", port=5038, username="admin", secret="x")
    )
    assert status.connected is True
    assert status.provider == "null"


@pytest.mark.asyncio
async def test_null_provider_fails_on_missing_params():
    provider = NullAsteriskProvider()
    status = await provider.get_status(
        ConnectionParams(host="", port=5038, username="", secret="")
    )
    assert status.connected is False


def test_factory_defaults_to_null(monkeypatch):
    reset_asterisk_provider()
    from app.core import config
    monkeypatch.setattr(config.settings, "TELEPHONY_PROVIDER",
                        TelephonyProvider.NULL.value, raising=False)
    provider = get_asterisk_provider()
    assert isinstance(provider, NullAsteriskProvider)
    reset_asterisk_provider()


def test_factory_switches_to_ami_by_config_only(monkeypatch):
    """Switching providers is configuration, not code: flip the setting and the
    factory yields the real AMI adapter (no upstream change)."""
    reset_asterisk_provider()
    from app.core import config
    monkeypatch.setattr(config.settings, "TELEPHONY_PROVIDER",
                        TelephonyProvider.AMI.value, raising=False)
    provider = get_asterisk_provider()
    assert isinstance(provider, AmiAsteriskProvider)
    reset_asterisk_provider()


def test_null_provider_parses_events_case_insensitively():
    provider = NullAsteriskProvider()
    evt = provider.parse_event({"Event": "Newchannel", "Channel": "SIP/100"})
    assert evt is not None and evt.event_type == "Newchannel" and evt.channel == "SIP/100"
    assert provider.parse_event({"nope": 1}) is None


# --------------------------------------------------------------------------- #
# Secret encryption at rest
# --------------------------------------------------------------------------- #
def test_secret_encrypts_and_round_trips():
    token = encrypt_secret("sup3r-s3cret")
    assert token != "sup3r-s3cret"          # never stored plaintext
    assert decrypt_secret(token) == "sup3r-s3cret"


def test_decrypt_rejects_tampered_token():
    with pytest.raises(ValueError):
        decrypt_secret("not-a-valid-fernet-token")


# --------------------------------------------------------------------------- #
# Hybrid resolution (repository rule)
# --------------------------------------------------------------------------- #
def _repo():
    from app.repositories.telephony_repository import TelephonyConnectionRepository
    ctx = SimpleNamespace(company_id="company-1", is_super_admin=False)
    return TelephonyConnectionRepository(SimpleNamespace(), ctx)


@pytest.mark.asyncio
async def test_resolve_effective_prefers_company_override():
    repo = _repo()
    company_row = SimpleNamespace(id="c-conn", enabled=True)
    default_row = SimpleNamespace(id="p-conn", enabled=True)

    async def company_conn(cid):
        return company_row

    async def platform_default():
        return default_row

    repo.get_company_connection = company_conn
    repo.get_platform_default = platform_default

    source, row = await repo.resolve_effective("company-1")
    assert source == "company" and row is company_row


@pytest.mark.asyncio
async def test_resolve_effective_falls_back_to_platform_default():
    repo = _repo()
    default_row = SimpleNamespace(id="p-conn", enabled=True)

    async def no_company(cid):
        return None

    async def platform_default():
        return default_row

    repo.get_company_connection = no_company
    repo.get_platform_default = platform_default

    source, row = await repo.resolve_effective("company-1")
    assert source == "platform-default" and row is default_row


@pytest.mark.asyncio
async def test_resolve_effective_returns_none_when_nothing_available():
    repo = _repo()

    async def none_(*a, **k):
        return None

    repo.get_company_connection = none_
    repo.get_platform_default = none_

    source, row = await repo.resolve_effective("company-1")
    assert source == "none" and row is None


# --------------------------------------------------------------------------- #
# Service contract
# --------------------------------------------------------------------------- #
class FakeSession:
    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def _service(ctx):
    from app.services.telephony_service import TelephonyService
    repo = SimpleNamespace(ctx=ctx)
    audit = SimpleNamespace()

    async def record(**kwargs):
        return None

    audit.record = record
    svc = TelephonyService(FakeSession(), repo, audit)
    return svc, repo


@pytest.mark.asyncio
async def test_test_connection_probes_and_persists_status():
    reset_asterisk_provider()  # ensure Null provider
    ctx = SimpleNamespace(company_id="company-1", is_super_admin=False)
    svc, repo = _service(ctx)

    row = SimpleNamespace(
        id="conn-1", company_id="company-1", enabled=True,
        host="pbx.local", port=5038, ami_username="admin",
        ami_secret_encrypted=encrypt_secret("s"), use_tls=False,
        last_status=TelephonyConnectionStatus.UNKNOWN.value,
    )
    persisted = {}

    async def get_scoped(cid):
        return row

    async def update(obj, **fields):
        persisted.update(fields)
        return obj

    repo.get_scoped = get_scoped
    repo.update = update

    result = await svc.test_connection("conn-1", actor_id="u1")
    assert result.connected is True
    assert persisted["last_status"] == TelephonyConnectionStatus.CONNECTED.value


@pytest.mark.asyncio
async def test_create_blocked_for_non_super_admin():
    """Provider-managed: only super admins manage PBX connections."""
    from app.core.exceptions import PermissionDeniedError
    from app.schemas.telephony import TelephonyConnectionCreate
    ctx = SimpleNamespace(company_id="company-1", is_super_admin=False)
    svc, _ = _service(ctx)

    payload = TelephonyConnectionCreate(
        name="Platform PBX", host="pbx.local", ami_username="admin",
        ami_secret="secret",
    )
    with pytest.raises(PermissionDeniedError):
        await svc.create_connection(payload, actor_id="u1")


@pytest.mark.asyncio
async def test_super_admin_creates_platform_connection():
    from app.schemas.telephony import TelephonyConnectionCreate
    ctx = SimpleNamespace(company_id=None, is_super_admin=True)
    svc, repo = _service(ctx)
    created = {}

    async def get_platform_default():
        return None  # none yet

    async def create(**kw):
        created.update(kw)
        return SimpleNamespace(id="conn-1", **kw)

    repo.get_platform_default = get_platform_default
    repo.create = create

    payload = TelephonyConnectionCreate(
        name="Platform PBX", host="pbx.local", ami_username="admin",
        ami_secret="secret",
    )
    row = await svc.create_connection(payload, actor_id="admin-1")
    assert row.company_id is None                       # platform-owned
    assert created["ami_secret_encrypted"] != "secret"  # encrypted at rest


@pytest.mark.asyncio
async def test_super_admin_create_conflicts_when_connection_exists():
    from app.core.exceptions import ConflictError
    from app.schemas.telephony import TelephonyConnectionCreate
    ctx = SimpleNamespace(company_id=None, is_super_admin=True)
    svc, repo = _service(ctx)

    async def get_platform_default():
        return SimpleNamespace(id="existing")

    repo.get_platform_default = get_platform_default

    payload = TelephonyConnectionCreate(
        name="Second", host="pbx2.local", ami_username="admin", ami_secret="s",
    )
    with pytest.raises(ConflictError):
        await svc.create_connection(payload, actor_id="admin-1")
