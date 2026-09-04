# Assistant platform — weeks 1–3 contract

The slice that turns ASTRA from *an AI sysadmin* into *a platform that can host AI
sysadmins*. All three weeks have shipped.

## Naming

Internally these are **assistants**, not agents. In this codebase "agent" already means the
Windows service on the device — `api/v1/agent.py`, `agent_enrollment_key`,
`agent_update.py`, `AstraAgent.Service`. The product may still call them Agents to
customers; the schema must not, or every future reference is ambiguous.

---

## Week 1 — shipped

Migration `0056_assistants`. Two tables, no change to any existing table.

### `assistants`

| Column | Meaning |
|---|---|
| `org_id` | NULL = built-in, owned by the platform operator, readable by every org. Same convention `knowledge_articles` uses for global articles. |
| `published_version_id` | The version currently served. A pointer, not a status flag: "which words did a human approve" is a question only a pointer answers. No FK — `assistant_versions` already points back, and a circular constraint buys integrity this codebase does not enforce on comparable columns. |
| `archived` | Soft delete. Traces reference assistants by id long after anyone stops using one. |

### `assistant_versions`

`version_no` is monotonic per assistant, allocated server-side. `status` is
`draft` / `published` / `archived`.

**Every behaviour column is nullable, and NULL means "use the server default."** That is
the property that makes this safe to add to a running system — a row full of NULLs behaves
exactly as ASTRA does today.

| Column | NULL means |
|---|---|
| `system_prompt` | today's `WINDOWS_EXPERT_PROMPT` |
| `model` | `settings.ai_model` — column exists, **not honoured yet**; the API refuses a non-NULL value (see Week 2) |
| `max_tokens` | `settings.ai_max_tokens` — same |
| `max_tool_iterations` | `settings.ai_max_tool_iterations` — and that value is a **ceiling**, see below |
| `tool_ids` | every tool the engine advertises today |

`tool_ids = []` is **not** the same as NULL: it means this assistant may call nothing, which
is a legitimate answer-only configuration.

Only one prompt column, though `cognitive.py` chooses between two today. The second
(`SYSTEM_PROMPT`) goes to the built-in rule providers, and those ignore a system prompt
entirely — modelling text nobody reads would be modelling a no-op.

### The step cap is a ceiling, not a default

Each tool-use iteration is a billed model call, so a version that could *raise*
`max_tool_iterations` would be a tenant-writable multiplier on the AI bill. A version may
only come in **under** the server setting.

Enforced twice on purpose — the same defence in depth as the backend action registry and
the agent's own hardcoded allowlist:

* `AssistantVersionCreate` refuses a value above `settings.ai_max_tool_iterations` (422).
* `AssistantVersion.resolved()` clamps regardless, so a row written by a seed script, a
  fixture or a migration cannot get past it either.

Raising the limit for everyone stays an operator decision: `ASTRA_AI_MAX_TOOL_ITERATIONS`.

### Grants are a filter, never a grant of privilege

`tool_ids` narrows what an assistant may call. It cannot widen it. The remediation
registry's `tier` and `operator_only` rules still apply on top, so an id listed here that
the registry withholds stays withheld. Nothing in this table can promote an action.

---

## API

Base `/api/v1/assistants`. All endpoints org-scoped through the caller's JWT.

| Method | Path | Role | Notes |
|---|---|---|---|
| `GET` | `/assistants` | any | Org's own + all built-ins, non-archived |
| `POST` | `/assistants` | staff | 201 |
| `GET` | `/assistants/{id}` | any | Includes `versions[]`, newest first |
| `PATCH` | `/assistants/{id}` | staff | Name/description only — never behaviour |
| `DELETE` | `/assistants/{id}` | staff | Archive, 204 |
| `POST` | `/assistants/{id}/versions` | staff | Always creates a **draft** |
| `PATCH` | `/assistants/{id}/versions/{vid}` | staff | Drafts only |
| `POST` | `/assistants/{id}/versions/{vid}/publish` | **admin** | Rollback = publish an older version |

"staff" = `admin` or `technician`.

### Why publish is admin-only

A version decides which tools a model may reach. Promoting one is a privilege change — the
same reason approving a higher-tier remediation is not a technician's call. The check lives
in the service beside the audit entry, not in a route dependency, so the privilege boundary
and its record stay in one place.

### Refusals

| Situation | Status | Why |
|---|---|---|
| Another org's assistant | `404` | A tenant should not learn it exists |
| Editing a built-in (`org_id` NULL) | `400` | Platform-owned; fork it instead |
| Editing a published version | `400` | Published versions are immutable |
| Technician publishing | `400` | Admin-only |
| End user creating | `403` | `require_roles` |

### Audit

`assistant.create`, `assistant.update`, `assistant.archive`,
`assistant.version.create`, `assistant.publish`. The publish entry carries
`version_id`, `version_no` and `previous_version_id`, so a rollback is reconstructible.

### Seeding

`backend/scripts/seed_builtin_assistant.py`, idempotent, safe on every deploy. The prompt
is **not** copied into the migration — it lives in `app/services/ai/prompts.py`, and a
migration holding a second copy would go stale the first time it is tuned.

---

## Week 2 — engine reads the row

One production call site: `app/services/conversations.py:359`.

```python
version = await AssistantService(self.session).published_builtin()
CognitiveEngine(self.session, provider=provider, version=version)
```

`version` defaults to `None`, which means "behave as today". Resolution runs through
`AssistantVersion.resolved(defaults=...)`, the single place that decides what NULL means.

**Selection rule:** the published version of the platform's built-in assistant, or `None`
when nothing has been seeded. No `Conversation.assistant_id` column and no
`Organization.default_assistant_id` yet — there is exactly one assistant to choose from, so
a column to choose with would be a column with one legal value. Add it when an org can own
a default worth pointing at.

**`model` and `max_tokens` are not honoured.** The engine does not build the provider —
`ConversationService._route` does, choosing between the free built-in paths and the real LLM
on cost — so a per-version model means threading the version through that decision. Until
then `AssistantVersionCreate` **refuses** a non-NULL value rather than accepting and
ignoring it: silently-ignored configuration is the worse failure, because someone sets a
cheaper model, sees no change in the bill, and cannot tell whether they were ignored.

**Unchanged, deliberately:**

- The `_is_real_llm()` branch. Built-in rule providers keep receiving the existing
  `SYSTEM_PROMPT` constant; nothing about the free paths changes.
- The prompt-cache arrangement. Invariant text first carrying the `cache_control`
  breakpoint, the hostname sentence after it. Reordering these would put a hostname inside
  the cached prefix and give every device its own copy of an identical brief.
- Tool dispatch. `dispatch_tool` keeps its signature; grants filter the *advertised* list
  before the model sees it, which is the same shape `escalation_tools.available_for()`
  already uses to withhold ticket tools from orgs that cannot raise tickets.
- Escalation wording. The condition became `any(name == OFFER)` over the *filtered* list
  instead of `len(tools) > len(TOOL_SCHEMAS)`, so an assistant not granted the offer tool
  is never told to call it. Equivalent when no grant is set: `available_for()` returns
  either nothing or the whole escalation set, never a partial one.

### Cost

Unchanged today, and that is verified rather than assumed — the equivalence test pins the
model's input as byte-identical, so token spend per turn cannot have moved.

* **Cache prefix.** Still one prefix across the whole fleet: the seed script sets
  `system_prompt` to exactly `WINDOWS_EXPERT_PROMPT`, and there is one assistant. Prefixes
  fragment only when organizations publish assistants with *different* prompts — at which
  point the measured $0.025/turn is worth re-measuring, because the fleet-wide cache hit
  rate is what it rests on.
* **New query.** One indexed join per chat turn (`published_builtin()`). Not on the
  heartbeat or telemetry paths.
* **Step cap.** See "The step cap is a ceiling" above — the one place this table could have
  raised the bill, closed in two layers.

## Week 3 — proof

`backend/tests/test_assistant_runtime.py` — 7 tests, and the two that matter:

1. **Equivalence.** With the seeded built-in version, the system blocks and the advertised
   tool set are byte-identical to what they were before assistant versions existed. This is
   what makes "nothing broke" a verified claim rather than a belief.
2. **Isolation.** A grant narrows and can never widen. An assistant granted only
   `list_devices` never sees `propose_remediation`; naming a tool that does not exist does
   not create it; and granting `propose_remediation` hands over the tool, not the
   catalogue — admin-only and `operator_only` actions stay filtered out in `tools.py`, so no
   row a tenant can write puts them back.

The recorder in these tests is deliberately **not** a `StubProvider` subclass. The built-in
providers read no system prompt, so a stub-derived recorder would capture the fallback
constant and prove nothing about what a version actually sends.

---

## Not in this slice

Workflow engine · workflow canvas · MCP · third-party integrations · Slack · model routing ·
autonomy levels · `runs`/`run_steps` trace tables · evaluation harness · templates gallery.

`runs`/`run_steps` is the next one (weeks 6–7 of the 90-day plan), not part of this.
