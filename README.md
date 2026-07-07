# Project ASTRA

Enterprise AI Operations Platform — an AI System Administrator that automates IT support using AI reasoning, endpoint telemetry, enterprise knowledge, and secure automation.

## Products

| Product | Path | Stack |
|---|---|---|
| ASTRA Backend API | [`backend/`](backend/) | Python · FastAPI · SQLAlchemy · PostgreSQL · Redis · Qdrant |
| ASTRA Web Portal | [`portal/`](portal/) | Next.js · TypeScript · Tailwind · shadcn/ui |
| ASTRA Windows Agent | [`agent/`](agent/) | C# .NET 8 · Windows Service + tray app |
| Infrastructure | [`infra/`](infra/) | Docker Compose · PostgreSQL 16 · Redis 7 · Qdrant |

## Quick start (local dev)

```bash
# 1. Infrastructure
cp infra/.env.example infra/.env   # then set real passwords
docker compose -f infra/docker-compose.yml up -d

# 2. Backend / portal — see each workspace's README once scaffolded
```

## Development

This repo is developed with Claude Code. Project rules live in [CLAUDE.md](CLAUDE.md); specialist subagents (architect, backend-dev, frontend-dev, windows-agent-dev, devops-engineer, qa-engineer, security-reviewer) live in [.claude/agents/](.claude/agents/).

Build order: infra + auth → devices + agent heartbeat → telemetry + dashboard → AI engine + knowledge base → self-healing → assets/reporting/notifications.
