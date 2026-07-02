# SMS Campaign Engine — Implementation Report

Built on top of the SMS Foundation. Reuses existing RBAC, auth, tenant context,
repository + service layers, audit infrastructure, and the Angular layout.

Scope: campaigns (create / edit-draft / schedule / send-now / cancel / history),
recipient resolution, rendering engine, and the dispatcher abstraction. Analytics
and real SMS providers are intentionally **not** included.

---

## New tables / migration order

No new tables. `sms_campaigns`, `sms_campaign_recipients`, `sms_messages` already
exist (migrations 0015–0017) with models in place.

One **additive** migration:

```
… → 0018_sms_sender_tenant_unique
   → 0019_sms_campaign_source_and_indexes   ← NEW
```

`0019` adds:
- `sms_campaigns.source_list_id` (FK → contact_lists, ON DELETE SET NULL) — the
  chosen list when `source_type = 'contact_list'`,
- index `ix_sms_campaigns_company_status` (campaign history listing),
- indexes `ix_sms_campaign_recipients_campaign`, `ix_sms_messages_campaign`.

Run with `alembic upgrade head`. Additive only — safe on top of 0013–0018.

---

## New permission

| Permission | Granted to | Gates |
|---|---|---|
| `sms.send` | company_admin | schedule / send / cancel a campaign |

Authoring (create/edit-draft/read) uses the existing `sms.manage` / `sms.read`.

---

## New APIs (prefix `/api/v1/sms/campaigns`)

| Method | Path | RBAC |
|---|---|---|
| GET | `/sms/campaigns` | sms.read or sms.manage |
| POST | `/sms/campaigns` | sms.manage |
| GET | `/sms/campaigns/{id}` | sms.read or sms.manage |
| PATCH | `/sms/campaigns/{id}` (draft only) | sms.manage |
| POST | `/sms/campaigns/{id}/schedule` | sms.send |
| POST | `/sms/campaigns/{id}/send` | sms.send |
| POST | `/sms/campaigns/{id}/cancel` | sms.send |
| GET | `/sms/campaigns/{id}/recipients` | sms.read or sms.manage |
| GET | `/sms/campaigns/{id}/messages` | sms.read or sms.manage |

List + message endpoints support pagination, search, and status filtering.

---

## Recipient resolution layer

`app/services/sms_recipient_resolver.py` converts a campaign source into a frozen
recipient set:
- **Contact list** → all members with a mobile number.
- **Individual contacts** → the selected contacts with a mobile number.
- **Dedupe** by `mobile_e164` (first occurrence wins).
- **Snapshot** `phone_e164` + `resolved_name` onto `sms_campaign_recipients`;
  `contact_id` is a soft link (SET NULL on contact delete) so later
  edits/deletions never alter campaign history.
- Tenant-safe: contacts/lists load through tenant-scoped repositories.

For a contacts-source draft, the selection is snapshotted at create/edit; at send
the set is re-resolved (refreshes phone/name) then frozen.

---

## SMS rendering engine

`app/services/sms_renderer.py`:
- `extract_variables(body)` — distinct `{{tokens}}` in first-seen order,
- `render_template(body, values)` — substitutes known values; **unknown/missing
  tokens are left intact** (visible, not silently dropped),
- `missing_variables(body, values)` — missing-variable detection,
- `unsupported_variables(body)` — variables outside the supported catalog,
- `SUPPORTED_VARIABLES = (name, phone, company)` + `build_recipient_values(...)`
  are the **single extension point** — add a variable there, no machinery change.

---

## SMS dispatcher abstraction

`app/services/sms_provider.py`:
- `SmsProvider` protocol — one method `send(recipient_phone, content, sender_id)
  -> SendResult(status, provider_message_id, error_details)`,
- `NullSmsProvider` — simulation backend (no network I/O; returns a `sim-…`
  provider id), used for development/testing,
- `get_sms_provider()` factory — the single switch-point.

Future SMPP / AkashSMS / Twilio / HTTP-gateway providers implement the same
method and are returned by the factory — **no campaign service / route / UI
change**. Correlation seams already on `sms_messages`: `provider_message_id`
(returned by the provider) and `delivered_at` (for a future receipt webhook).

---

## Campaign lifecycle

```
draft ──schedule──▶ scheduled ──send──▶ processing ──▶ completed / failed
  │                     │
  └────────send─────────┘   (send-now works from draft or scheduled)
draft / scheduled ──cancel──▶ cancelled
```

- Editing allowed only in **draft**.
- Send/schedule validate the sender is **approved + active** and the template
  exists.
- Send freezes recipients, renders per-recipient (snapshotting sender label +
  rendered body onto each `sms_messages` row), dispatches via the provider,
  updates counters, sets final status.
- Audited: create / update / schedule / send / cancel.

---

## File manifest

### New backend files
- `app/repositories/sms_campaign_repository.py`
- `app/services/sms_campaign_service.py`
- `app/services/sms_recipient_resolver.py`
- `app/api/v1/routes/sms_campaign.py`
- `alembic/versions/0019_sms_campaign_source_and_indexes.py`

### Modified backend files
- `app/core/constants.py` — add `SMS_SEND` + grant; add `SmsCampaignSource` enum.
- `app/services/sms_renderer.py` — variable validation / missing detection / extensibility.
- `app/services/sms_provider.py` — formal `SmsProvider` interface + `SendResult`.
- `app/models/sms.py` — add `SmsCampaign.source_list_id`.
- `app/schemas/sms.py` — campaign / recipient / message schemas.
- `app/api/v1/deps.py` — `get_sms_campaign_service`.
- `app/api/v1/router.py` — register the campaign router.

### New frontend files (`src/app/features/sms/`)
- `sms-campaign-list.component.ts`
- `sms-campaign-form.component.ts` (create/edit draft, source picker)
- `sms-campaign-detail.component.ts` (KPIs, recipients + messages tabs, send/schedule/cancel)

### Modified frontend files
- `features/sms/sms.models.ts` — campaign types.
- `features/sms/sms.service.ts` — campaign API client.
- `app.routes.ts` — `/sms/campaigns`, `/campaigns/new`, `/campaigns/:id`, `/campaigns/:id/edit`.
- `layout/navigation.ts` — "SMS Campaigns" nav entry.
- `core/constants/rbac.constants.ts` — `SmsSend` permission.

---

## Verification

- **Backend:** 16/16 end-to-end checks against live PostgreSQL — draft create,
  recipient resolution (dedupe + drop no-phone + snapshot), draft edit + source
  switch, send blocked when sender unapproved, send→completed with rendered &
  snapshotted messages + provider ids, completed-campaign edit/cancel guards,
  schedule + cancel, past-schedule rejection, history list + status filter,
  tenant isolation, audit logging.
- **Migrations:** 0013→0019 apply cleanly; `source_list_id` + indexes verified.
- **Frontend:** production build succeeds; campaign list / form / detail emit
  lazy chunks; Playwright smoke test 7/7 (list, form with source picker, detail
  with KPIs + tabs). See `screenshots/`.
