# Security Policy

ASTRA runs commands on customer endpoints, so we treat the command path as the most
sensitive code we own. We welcome and reward responsible disclosure.

## Reporting a vulnerability

Please email **security@yourdomain.com** (update this to your real address) with:

- a description of the issue and its impact,
- steps to reproduce (proof-of-concept if possible),
- affected component (backend / portal / Windows agent) and version/commit.

Do **not** open a public GitHub issue for security reports. We aim to acknowledge
within 3 business days and to provide a remediation timeline after triage. Please
give us a reasonable window to fix before any public disclosure.

A machine-readable contact is published at `/.well-known/security.txt` (RFC 9116).

## Scope

- Backend API (`backend/`)
- Web portal (`portal/`)
- Windows agent (`agent/`)

## Our security model (summary)

- **Two independent allowlists** gate remediation: a signed server-side action
  registry *and* a hardcoded allowlist in the agent. The agent executes action IDs,
  never arbitrary command strings — anything unknown is refused.
- **Approval tiers** (`automatic` / `approval_required` / `admin_only`) are enforced
  server-side; the agent only ever runs *approved* tasks, and an `admin_only` action
  can never dispatch without explicit admin approval (covered by a regression test).
- **Blast-radius controls**: a per-organization circuit breaker suspends automatic
  approval and hard-caps remediation volume in a rolling window.
- **Tokens**: short-lived access tokens with single-use rotating refresh tokens and
  refresh-token *reuse detection* (a replayed token revokes the whole family).
- **Multi-tenant isolation** is enforced in every repository/service by `org_id`.
- **Audit logs** record every mutation and every agent command.

## Roadmap (in progress)

- Per-command cryptographic signing verified by the agent against a pinned key.
- Managed secrets store + key rotation; mTLS between agent and backend.
- Continuous dependency / SAST / secret / container scanning in CI.
- Third-party penetration test before first enterprise customer, then annually.
