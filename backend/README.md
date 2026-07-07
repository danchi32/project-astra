# ASTRA Backend API

FastAPI backend for the ASTRA platform. See root [CLAUDE.md](../CLAUDE.md) for architecture rules.

## Current state — Phase 1: Auth + Schema

- JWT auth: login, refresh (single-use rotating refresh tokens), logout, `/auth/me`
- RBAC roles: `admin`, `technician`, `user` — enforced via FastAPI dependencies
- Org-scoped user management (admins manage users; cross-org access returns 404)
- Audit log written for every mutation (login, user create/update/delete)
- Alembic migration `0001` — organizations, users, refresh_tokens, audit_logs

## Setup

Requires Python 3.11+ (note: 3.14 **beta** builds are incompatible with pydantic).

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env   # then set real values

# Start infra (from repo root), apply migrations, seed the first admin
docker compose -f ../infra/docker-compose.yml up -d
.venv\Scripts\python -m alembic upgrade head
$env:ASTRA_BOOTSTRAP_PASSWORD = "a-long-secure-password"
.venv\Scripts\python -m scripts.create_admin --org "Acme Corp" --email admin@acme.com --name "Jane Admin"

# Run the API — docs at http://localhost:8000/docs
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Tests

```powershell
.venv\Scripts\python -m pytest
```

Tests run against in-memory SQLite (no Docker needed) and cover security boundaries first: RBAC denial, refresh-token rotation/replay, org isolation, session revocation on deactivation.

## Layout

```
app/
├── api/            # routers + auth dependencies (thin — no business logic)
├── core/           # config (pydantic-settings), security (JWT/bcrypt), database
├── models/         # SQLAlchemy models
├── repositories/   # all DB access
├── schemas/        # Pydantic request/response models
└── services/       # business logic, audit logging, domain errors
alembic/            # migrations
scripts/            # create_admin bootstrap
tests/              # pytest suite
```
