# Authentication & Authorization Module

Production-ready auth foundation for the Telecom SaaS platform. Built on the
approved Clean Architecture (Routes → Services → Repositories → Models) with
multi-tenant isolation and RBAC.

## What's included

| Requirement | Implementation |
|---|---|
| JWT access tokens | `core/security.py` — 15-min lifetime, carries `sub`, `company_id`, `roles`, `permissions`, `jti` |
| Refresh tokens | Server-side records (`models/refresh_token.py`) with **rotation** and **reuse detection** |
| Login | `services/auth_service.py` — generic errors, timing-attack mitigation, lockout |
| Logout | Refresh-token revocation |
| Password hashing | bcrypt via passlib, configurable cost, transparent rehash on login |
| Password reset | Short-lived reset JWT; revokes all sessions on success |
| RBAC | `core/rbac.py` + `core/constants.py` — role→permission catalog |
| Role guards | `require_role(...)` dependency |
| Permission checks | `require_permission(...)` dependency (ALL-of semantics) |
| Roles | super_admin (platform), company_admin, company_user |

## Layers

```
api/v1/routes/auth.py     HTTP endpoints (7 routes)
api/v1/deps.py            DI chain + RBAC guards
services/auth_service.py  use cases, owns transactions, raises domain errors
repositories/             tenant-scoped data access (base auto-scopes by company_id)
models/                   SQLAlchemy ORM (PG-native UUID / JSONB / CITEXT)
schemas/                  Pydantic request/response DTOs
core/                     config, security, rbac, exceptions, error handlers, logging
db/                       base, session, init_db (idempotent seed)
```

## Endpoints (under `/api/v1`)

```
POST /auth/login            -> { access_token, refresh_token, expires_in }
POST /auth/refresh          -> rotates the token pair
POST /auth/logout           -> 204, revokes the refresh token
GET  /auth/me               -> identity + resolved roles/permissions
POST /auth/change-password  -> 204, revokes all sessions
POST /auth/forgot-password  -> 202, enumeration-safe (always same response)
POST /auth/reset-password   -> 204, revokes all sessions
```

## Security best practices applied

- **Credential responses are generic** — login never reveals whether the email
  or password was wrong; forgot-password always returns the same body.
- **Timing-attack mitigation** — a dummy hash verify runs even when the user is
  absent, keeping response time comparable.
- **Account lockout** — status flips to `locked` after `MAX_FAILED_LOGINS`.
- **Refresh-token rotation + theft detection** — each refresh issues a new token
  and revokes the old; presenting a rotated-out token revokes the whole family.
- **Secrets are hashed at rest** — refresh tokens and API keys stored as SHA-256
  digests; passwords as bcrypt. Response models never expose hashes.
- **Strict request schemas** — `extra="forbid"` blocks mass assignment.
- **Password policy** — length + upper/lower/digit enforced in schemas.
- **Tenant isolation** — `company_id` derived from the JWT, never client input;
  the base repository auto-scopes every query.
- **Token type enforcement** — an access token can't be used where a refresh or
  reset token is required, and vice versa.
- **No secret leakage in logs** — logging filter redacts password/token fields;
  unhandled errors return a sanitized 500 with a correlation `request_id`.
- **Sessions invalidated on credential change** — change/reset revoke all
  refresh tokens.

## Running

```bash
pip install -r requirements.txt
cp .env.example .env            # set a real JWT_SECRET_KEY for production
# create tables via Alembic (recommended) then seed:
python -c "import asyncio; from app.db.session import AsyncSessionLocal; \
from app.db.init_db import run_seed; \
asyncio.run((lambda: AsyncSessionLocal().__aenter__())())"  # see init_db.run_seed
uvicorn app.main:app --reload
```

Seed via `app.db.init_db.run_seed(session, email, password)` — idempotent;
creates the 3 system roles, the permission catalog, role→permission mappings,
and a bootstrap super admin.

## Dependency pins (discovered through integration testing)

- `fastapi==0.115.6` — 0.137.x has a nested-router flattening regression.
- `bcrypt==4.0.1` — passlib is incompatible with bcrypt ≥ 4.1.

## Verified by tests

- End-to-end (live ASGI + DB): login, /me, refresh rotation, rotated-token
  rejection, wrong-password 401, unauthenticated 401, account lockout.
- Guards: permission grant/denial, multi-permission, role guards, super-admin
  bypass.
- Seed: idempotency, 3 roles, single platform super admin, password verifies.
