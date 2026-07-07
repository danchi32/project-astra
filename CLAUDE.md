# Project ASTRA — Enterprise AI Operations Platform

AI System Administrator SaaS: web portal + Windows desktop agent + FastAPI backend + AI reasoning engine that automates IT support using telemetry, enterprise knowledge, and secure automation.

## Monorepo layout

| Path | Product | Stack |
|---|---|---|
| `backend/` | ASTRA Backend API | Python, FastAPI, SQLAlchemy, JWT auth |
| `portal/` | ASTRA Web Portal | Next.js, TypeScript, Tailwind, shadcn/ui, React Query + Zustand |
| `agent/` | ASTRA Windows Agent | C# .NET 8 — Windows Service + tray app |
| `infra/` | Infrastructure | Docker Compose: PostgreSQL, Redis, Qdrant |
| `docs/` | Documentation | Architecture, API docs, install/deploy guides |

## Design principles (non-negotiable)

1. **Evidence Before Action** — the AI engine must gather telemetry/knowledge before proposing any remediation.
2. **Human-in-the-Loop** — remediations are tiered: `automatic` / `approval_required` / `admin_only`. Never let a lower tier execute a higher-tier action.
3. **Least Privilege** — agent executes only allowlisted, approved commands. RBAC everywhere in the API.
4. **API First** — portal and Windows agent are both pure API clients. No business logic in clients.

## Coding rules

- Clean Architecture + SOLID. Backend uses repository pattern + dependency injection (FastAPI `Depends`).
- Never hardcode secrets — everything via environment variables (`.env` locally, never committed).
- Every API endpoint: documented (OpenAPI), validated (Pydantic), authorized (RBAC dependency), audited (audit log entry for mutations).
- Write unit tests alongside each feature (pytest / Vitest / xUnit). Integration tests per module.
- Migrations via Alembic — never edit the DB schema by hand.

## Security requirements

RBAC, JWT (short-lived access + refresh), HTTPS only, audit logs for all mutations and all agent commands, encryption at rest and in transit, device certificates for agent enrollment, least privilege.

Self-healing action tiers:
- **automatic**: restart Explorer/services/Outlook/Teams/Zoom, flush DNS, clear temp, restart adapter
- **approval_required**: Office repair, driver update, network reset
- **admin_only**: registry, BIOS, firmware, Windows reinstall

## AI engine

Workflow: intent recognition → knowledge search (Qdrant) → telemetry collection → confidence score → decision tree → self-healing → verification → learning. Built as an agentic tool-use loop; each step is a tool the model calls. Approval tiers are enforced in code (backend), never only in the prompt.

## Build roadmap (vertical slices, in order)

1. Docker infra + DB schema + Auth (JWT, RBAC) ✅
2. Devices API + Windows agent heartbeat (60s) + enrollment ✅
3. Telemetry collection (CPU/RAM/disk/events/apps/services/updates) + dashboard ✅
4. AI conversation + Cognitive Engine + Knowledge Base (Qdrant) ← current phase
5. Self-healing with approval tiers + audit logs
6. Assets, reporting, notifications

## UI theme

Modern enterprise SaaS — Microsoft Intune + ServiceNow + Linear + Notion. Dark and light mode from day one (CSS variables, no hardcoded colors).

## Agent team

Specialist subagents live in `.claude/agents/`. Delegate domain work to the matching specialist: `architect`, `backend-dev`, `frontend-dev`, `windows-agent-dev`, `devops-engineer`, `qa-engineer`, `security-reviewer`. Run `security-reviewer` before merging anything touching auth, agent commands, or remediation execution.

## Commands

- Infra up: `docker compose -f infra/docker-compose.yml up -d`
- Backend dev: `cd backend && uvicorn app.main:app --reload` (once scaffolded)
- Portal dev: `cd portal && npm run dev` (once scaffolded)
