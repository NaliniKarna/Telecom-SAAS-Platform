/**
 * Developer documentation content.
 *
 * IMPORTANT: every endpoint, field, and status code below reflects APIs that
 * actually exist in this project (verified against the FastAPI routers and
 * Pydantic schemas). No endpoints or features are invented. Base path is
 * /api/v1 and authentication is a JWT bearer token obtained from /auth/login.
 */
export interface DocTopic {
  id: string;
  group: string;
  title: string;
  keywords: string;
  html: string;
}

export const DOC_GROUPS = ['Get started', 'API reference'] as const;

export const DOC_TOPICS: DocTopic[] = [
  {
    id: 'getting-started',
    group: 'Get started',
    title: 'Getting started',
    keywords: 'base url json envelope pagination overview quickstart',
    html: `
      <p>The Telecom Console API is a JSON REST API. All endpoints are served under
      the version prefix <code>/api/v1</code> (for example
      <code>https://your-host/api/v1/auth/login</code>).</p>

      <h3>Request &amp; response format</h3>
      <p>Send and receive <code>application/json</code>. List endpoints return a
      consistent envelope with a <code>data</code> array and a <code>meta</code>
      object; errors return an <code>errors</code> array (see Error codes).</p>
      <pre>{
  "data": [ /* items */ ],
  "meta": { "page": 1, "size": 20, "total": 42, "pages": 3 }
}</pre>

      <h3>Pagination</h3>
      <p>Collection endpoints accept <code>page</code> (from 1) and
      <code>size</code> (1–100) query parameters. The <code>meta</code> block
      reports <code>page</code>, <code>size</code>, <code>total</code>, and
      <code>pages</code>.</p>

      <h3>Quick start</h3>
      <ol>
        <li>Register your company and sign in to obtain access.</li>
        <li>Call <code>POST /auth/login</code> to get an access token.</li>
        <li>Send the token as <code>Authorization: Bearer &lt;token&gt;</code> on every request.</li>
        <li>Add contacts, create a sender ID and template, then send an SMS campaign.</li>
      </ol>
    `,
  },
  {
    id: 'authentication',
    group: 'Get started',
    title: 'Authentication',
    keywords: 'login token bearer jwt refresh logout me session',
    html: `
      <p>Authentication uses JSON Web Tokens. Exchange your email and password for
      an access token, then send that token as a bearer credential on subsequent
      requests. Access tokens are short-lived; use the refresh token to obtain a
      new one without signing in again.</p>

      <h3>Log in</h3>
      <pre>POST /api/v1/auth/login
Content-Type: application/json

{ "email": "you@company.com", "password": "your-password" }</pre>
      <p>Response:</p>
      <pre>{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900
}</pre>

      <h3>Authorize requests</h3>
      <pre>curl https://your-host/api/v1/auth/me \\
  -H "Authorization: Bearer ACCESS_TOKEN"</pre>

      <h3>Refresh the access token</h3>
      <pre>POST /api/v1/auth/refresh
{ "refresh_token": "REFRESH_TOKEN" }</pre>
      <p>Returns a new token pair in the same shape as login.</p>

      <h3>Current user</h3>
      <p><code>GET /api/v1/auth/me</code> returns the authenticated user's profile
      and role.</p>

      <h3>Log out</h3>
      <p><code>POST /api/v1/auth/logout</code> with
      <code>{ "refresh_token": "..." }</code> revokes the refresh token and
      responds <code>204 No Content</code>.</p>
    `,
  },
  {
    id: 'api-keys',
    group: 'Get started',
    title: 'API keys',
    keywords: 'api key credentials generate revoke prefix programmatic',
    html: `
      <p>API keys are named credentials your company can issue for programmatic
      use. They are created and managed through the console or the endpoints
      below. The full key is shown <strong>once</strong> at creation — store it
      securely; afterwards only the key prefix is visible.</p>

      <h3>List keys</h3>
      <pre>GET /api/v1/api-keys?page=1&amp;size=20</pre>
      <p>Each item includes <code>id</code>, <code>name</code>,
      <code>key_prefix</code>, <code>status</code> (active / revoked / expired),
      <code>usage_count</code>, <code>last_used_at</code>, and
      <code>expires_at</code>.</p>

      <h3>Create a key</h3>
      <pre>POST /api/v1/api-keys
{
  "name": "Server integration",
  "description": "Backend service",
  "expires_at": null
}</pre>
      <p>Response (<code>201 Created</code>) — the only time <code>api_key</code>
      is returned in full:</p>
      <pre>{
  "id": "…",
  "name": "Server integration",
  "key_prefix": "tck_1a2b",
  "status": "active",
  "api_key": "tck_1a2b…FULL_SECRET",
  "usage_count": 0,
  "expires_at": null,
  "created_at": "2026-01-01T00:00:00Z"
}</pre>

      <h3>Revoke a key</h3>
      <pre>POST /api/v1/api-keys/{key_id}/revoke</pre>
      <p>Marks the key revoked; it can no longer be used.</p>

      <p class="note">These management endpoints are authorized with your bearer
      access token (see Authentication).</p>
    `,
  },
  {
    id: 'sms-api',
    group: 'API reference',
    title: 'SMS API',
    keywords: 'sms send campaign sender id template message schedule delivery analytics',
    html: `
      <p>Sending SMS is organized around <strong>campaigns</strong>. A campaign
      references an approved sender ID, a message template, and its recipients
      (a contact list or an explicit set of contacts). You then send it
      immediately or schedule it.</p>

      <h3>1. Create a sender ID</h3>
      <pre>POST /api/v1/sms/sender-ids
{ "name": "Acme", "sender_id": "ACME", "description": "Primary brand" }</pre>
      <p>Sender IDs are subject to approval before they can be used to send.</p>

      <h3>2. Create a template</h3>
      <pre>POST /api/v1/sms/templates
{ "name": "Welcome", "body": "Hi {{name}}, welcome to Acme." }</pre>
      <p>Template bodies support personalization placeholders such as
      <code>{{name}}</code>, <code>{{phone}}</code>, and <code>{{company}}</code>.</p>

      <h3>3. Create a campaign</h3>
      <pre>POST /api/v1/sms/campaigns
{
  "name": "January welcome",
  "sender_id": "SENDER_ID_UUID",
  "template_id": "TEMPLATE_ID_UUID",
  "source_type": "contact_list",
  "source_list_id": "LIST_UUID"
}</pre>
      <p>Set <code>source_type</code> to <code>"contact_list"</code> with a
      <code>source_list_id</code>, or <code>"contacts"</code> with a
      <code>contact_ids</code> array. A new campaign starts as a draft.</p>

      <h3>4. Send or schedule</h3>
      <pre>POST /api/v1/sms/campaigns/{id}/send

POST /api/v1/sms/campaigns/{id}/schedule
{ "schedule_time": "2026-02-01T09:00:00Z" }</pre>
      <p>A draft can also be cancelled with
      <code>POST /api/v1/sms/campaigns/{id}/cancel</code>.</p>

      <h3>Track delivery</h3>
      <p><code>GET /api/v1/sms/campaigns/{id}/messages</code> lists per-recipient
      messages and their delivery status. <code>GET /api/v1/sms/analytics</code>
      returns aggregate delivery/failure metrics.</p>
    `,
  },
  {
    id: 'contacts',
    group: 'API reference',
    title: 'Contacts',
    keywords: 'contacts recipients import lists segments tags mobile',
    html: `
      <p>Contacts are the recipients you message. Phone numbers are normalized to
      E.164 on save, and contacts can be grouped into lists for use as campaign
      recipients.</p>

      <h3>List contacts</h3>
      <pre>GET /api/v1/contacts?page=1&amp;size=20&amp;search=alex</pre>

      <h3>Create a contact</h3>
      <pre>POST /api/v1/contacts
{
  "first_name": "Alex",
  "last_name": "Rai",
  "mobile": "+9779800000000",
  "email": "alex@example.com",
  "tags": ["vip"],
  "status": "active"
}</pre>
      <p>The response includes both the raw and normalized numbers
      (<code>mobile_e164</code>).</p>

      <h3>Update &amp; delete</h3>
      <pre>GET    /api/v1/contacts/{id}
PATCH  /api/v1/contacts/{id}
DELETE /api/v1/contacts/{id}</pre>

      <h3>Bulk import</h3>
      <p>Preview a file before committing, then import:</p>
      <pre>POST /api/v1/contacts/import/preview
POST /api/v1/contacts/import</pre>

      <h3>Lists (segments)</h3>
      <p>Group contacts into lists to target them in campaigns:</p>
      <pre>POST /api/v1/contact-lists
POST /api/v1/contact-lists/{list_id}/members</pre>
    `,
  },
  {
    id: 'errors',
    group: 'API reference',
    title: 'Error codes',
    keywords: 'errors codes status 401 403 404 409 422 500 envelope validation',
    html: `
      <p>Errors use a uniform envelope. <code>data</code> is <code>null</code>,
      <code>meta.request_id</code> helps with support, and <code>errors</code>
      carries a machine-readable <code>code</code>, a human
      <code>message</code>, and optional <code>details</code>.</p>
      <pre>{
  "data": null,
  "meta": { "request_id": "…" },
  "errors": [
    { "code": "not_found", "message": "Resource not found", "details": null }
  ]
}</pre>

      <h3>Codes</h3>
      <table>
        <thead><tr><th>HTTP</th><th>Code</th><th>Meaning</th></tr></thead>
        <tbody>
          <tr><td>401</td><td><code>authentication_failed</code></td><td>Missing or invalid credentials.</td></tr>
          <tr><td>401</td><td><code>account_locked</code></td><td>Too many failed attempts.</td></tr>
          <tr><td>401</td><td><code>account_inactive</code></td><td>User or company is not active.</td></tr>
          <tr><td>403</td><td><code>permission_denied</code></td><td>Authenticated but not allowed.</td></tr>
          <tr><td>403</td><td><code>tenant_isolation_violation</code></td><td>Cross-tenant access blocked.</td></tr>
          <tr><td>404</td><td><code>not_found</code></td><td>Resource does not exist.</td></tr>
          <tr><td>409</td><td><code>conflict</code></td><td>Duplicate or conflicting state.</td></tr>
          <tr><td>422</td><td><code>validation_error</code></td><td>Request failed validation; see <code>details</code>.</td></tr>
          <tr><td>500</td><td><code>internal_error</code></td><td>Unexpected server error.</td></tr>
        </tbody>
      </table>
    `,
  },
];
