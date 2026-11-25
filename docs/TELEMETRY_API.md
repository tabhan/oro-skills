# Usage telemetry ingest API (contract)

Contract between the `aaxis-oro` plugin hooks (client) and the ingest service implemented in
`ai-ticketing` (server). The client side owns this document; change it here first.

Purpose: record who uses the plugin, on which project, and when. Metadata only.

## Never sent

Prompt text, file or code contents, environment variables, transcripts, credentials.
The client strips userinfo/tokens from remote URLs before sending.

## Endpoint

```
POST {BASE_URL}/telemetry/events
Content-Type: application/json
```

- Public, no authentication (the plugin cannot hold a secret).
- `BASE_URL` = `https://acp-api.aaxis.io` (production; the API has no global route prefix), so the full URL is
  `https://acp-api.aaxis.io/telemetry/events`.
- Body: max 32 KB. One request carries 1-50 events.
- The client only reports from inside an Oro project root (`bin/console` + `composer.lock` found at or above the working directory), for every event type.
- One `skill_used` per invocation: a typed `/aaxis-oro:x` and the Skill tool call it triggers within 120 s in the same session and agent count once.
- Client timeout: 3 s, fire-and-forget; the client never retries synchronously and never blocks a session.

### Request body

```json
{
  "schema": 1,
  "events": [ { "...": "Event, see below" } ]
}
```

### Event

| Field | Type | Req | Notes |
|---|---|---|---|
| `event_id` | string (UUID v4) | yes | Idempotency key; server must dedupe on it |
| `type` | enum | yes | `session_start`, `session_end`, `skill_used`, `command_used` |
| `occurred_at` | string (ISO 8601, with offset) | yes | Client clock |
| `session_id` | string (max 100) | yes | Claude Code session id |
| `user.git_name` | string (max 200) | no | `git config user.name` |
| `user.git_email` | string (max 320) | no | `git config user.email` |
| `user.os_user` | string (max 100) | no | |
| `client.hostname` | string (max 255) | no | |
| `client.os` | string (max 50) | no | e.g. `linux`, `darwin` |
| `client.plugin_version` | string (max 30) | yes | e.g. `0.29.1` |
| `client.claude_code_version` | string (max 30) | no | |
| `client.model` | string (max 100) | no | |
| `project.repo_url` | string (max 500) | no | Normalized `https://github.com/<owner>/<repo>`; null outside a git repo |
| `project.branch` | string (max 255) | no | |
| `project.commit` | string (max 64) | no | |
| `project.oro_version` | string (max 30) | no | From `composer.lock` |
| `data` | object | no | Per-type payload, below |

Per-type `data`:

| `type` | `data` |
|---|---|
| `session_start` | `{ "source": "startup" \| "resume" \| "clear" \| "compact" }` |
| `session_end` | `{ "reason": string, "duration_s": int, "prompt_count": int, "tool_count": int }` |
| `skill_used` | `{ "name": string }`  (e.g. `aaxis-oro:review`, `tab-jira`) |
| `command_used` | `{ "name": string }`  (an `aaxis-oro <subcommand>` invocation, subcommand only, no args) |

Example:

```json
{
  "schema": 1,
  "events": [{
    "event_id": "6f1c2b9e-3d4a-4e8b-9a51-0c7e2f1d8a33",
    "type": "session_start",
    "occurred_at": "2026-11-21T09:14:03+08:00",
    "session_id": "724555a3-c348-4f0d-9c8b-84a740e0a389",
    "user": { "git_name": "Jane Doe", "git_email": "jane@example.com", "os_user": "jane" },
    "client": { "hostname": "dev-01", "os": "linux", "plugin_version": "0.29.1",
                "claude_code_version": "2.3.1", "model": "claude-opus-5-5" },
    "project": { "repo_url": "https://github.com/acme/shop", "branch": "feature/ABC-123",
                 "commit": "824e757", "oro_version": "6.1.2" },
    "data": { "source": "startup" }
  }]
}
```

### Responses

| Status | Body | When |
|---|---|---|
| 202 | `{ "accepted": n, "duplicates": m }` | Stored (duplicates by `event_id` ignored) |
| 400 | `{ "error": "validation", "details": [...] }` | Whole batch rejected if `schema`/`events` malformed; individual invalid events are dropped and counted in `rejected` on 202 instead (`{ "accepted", "duplicates", "rejected" }`) |
| 413 | | Body > 32 KB |
| 429 | | Rate limit hit |

The client ignores all responses.

## Server requirements

- Validate with a schema; ignore unknown fields; truncate nothing silently (over-length = invalid event).
- Store server-side `received_at` and client IP alongside each event (IP may be hashed).
- Rate limit per IP: 120 events/min, 10 requests/10 s burst.
- No CORS needed (server-to-server). Requests come from `curl`/Python with **no `Origin` header and no API key**:
  the route must pass the API's cross-site request check (`apps/api/src/http-pipeline.ts`, `crossSiteRequestCheck`)
  for that case, e.g. by exempting `POST /telemetry/events` explicitly. Do not add a session/auth guard.
- Apply its own rate limit (the global `RateLimitGuard` defaults may not fit); see the limits above.
- Data is unauthenticated and can be forged: treat it as usage trends, not evidence.

### Storage (suggested)

Table `telemetry_event`: `event_id` (PK/unique), `type`, `occurred_at`, `received_at`, `session_id`,
`git_name`, `git_email`, `os_user`, `hostname`, `os`, `plugin_version`, `claude_code_version`, `model`,
`repo_url`, `branch`, `commit`, `oro_version`, `data` (jsonb), `client_ip`.
Indexes: `(occurred_at)`, `(git_email, occurred_at)`, `(repo_url, occurred_at)`.

## Read side (owner only)

Protected by the app's existing admin auth, restricted to the owner account.

```
GET {BASE_URL}/telemetry/events?from=&to=&email=&repo=&type=&limit=&cursor=
GET {BASE_URL}/telemetry/summary?from=&to=&group_by=user|repo|day
```

`summary` returns, per group: session count, distinct users/repos, total `duration_s`, last seen.
A simple admin page over these two endpoints is optional.
