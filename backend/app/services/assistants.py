"""CRUD for configurable AI assistants and their versions.

Nothing here runs a model. This service only decides what an assistant IS; the cognitive
engine learns to read it in a later, separately tested change.

Two rules shape every method:

  * A built-in assistant (org_id NULL) is the platform operator's, not the tenant's. Tenants
    read it — that is how they get ASTRA's own persona — and can never write it.
  * A published version is immutable. Editing behaviour means creating a draft; changing what
    is live means moving `published_version_id`, which is an audited act of its own.
"""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assistant,
    AssistantVersion,
    AssistantVersionStatus,
    User,
    UserRole,
)
from app.services.audit import AuditService
from app.services.exceptions import NotFoundError, ValidationError


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ── Reads ──────────────────────────────────────────────────────────────
    async def list_for_org(self, *, org_id: uuid.UUID) -> list[Assistant]:
        """The org's own assistants plus every built-in one, newest first."""
        rows = await self.session.execute(
            select(Assistant)
            .where(
                or_(Assistant.org_id == org_id, Assistant.org_id.is_(None)),
                Assistant.archived.is_(False),
            )
            .order_by(Assistant.created_at.desc())
        )
        return list(rows.scalars())

    async def get(self, *, org_id: uuid.UUID, assistant_id: uuid.UUID) -> Assistant:
        """Readable means: this org's, or built-in. Anything else is 404, not 403 — a
        tenant should not learn that another org's assistant exists."""
        row = await self.session.get(Assistant, assistant_id)
        if row is None or row.archived or (row.org_id is not None and row.org_id != org_id):
            raise NotFoundError("Assistant not found")
        return row

    async def published_builtin(self) -> AssistantVersion | None:
        """The published version of the platform's own assistant, or None if unseeded.

        None is a supported state, not a failure: the engine reads it as "run as ASTRA has
        always run". A deployment that has not run `scripts/seed_builtin_assistant.py` keeps
        working on the constants, which is what makes seeding a separate, unhurried step.
        """
        return await self.session.scalar(
            select(AssistantVersion)
            .join(Assistant, Assistant.published_version_id == AssistantVersion.id)
            .where(Assistant.org_id.is_(None), Assistant.archived.is_(False))
            .order_by(Assistant.created_at.asc())
            .limit(1)
        )

    async def versions(self, *, assistant_id: uuid.UUID) -> list[AssistantVersion]:
        rows = await self.session.execute(
            select(AssistantVersion)
            .where(AssistantVersion.assistant_id == assistant_id)
            .order_by(AssistantVersion.version_no.desc())
        )
        return list(rows.scalars())

    # ── Writes ─────────────────────────────────────────────────────────────
    async def create(self, *, actor: User, name: str, description: str | None) -> Assistant:
        row = Assistant(org_id=actor.org_id, name=name, description=description)
        self.session.add(row)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="assistant.create",
            target_type="assistant", target_id=str(row.id), detail={"name": name},
        )
        await self.session.commit()
        return row

    async def update(
        self, *, actor: User, assistant_id: uuid.UUID,
        name: str | None, description: str | None,
    ) -> Assistant:
        row = await self._writable(actor, assistant_id)
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="assistant.update",
            target_type="assistant", target_id=str(row.id),
        )
        await self.session.commit()
        return row

    async def archive(self, *, actor: User, assistant_id: uuid.UUID) -> None:
        """Soft delete. Traces and audit rows reference assistants by id long after anyone
        stops using one, so the row has to survive being 'deleted'."""
        row = await self._writable(actor, assistant_id)
        row.archived = True
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="assistant.archive",
            target_type="assistant", target_id=str(row.id),
        )
        await self.session.commit()

    async def create_version(
        self, *, actor: User, assistant_id: uuid.UUID, **fields
    ) -> AssistantVersion:
        """Always a draft. There is no way to create something already live."""
        assistant = await self._writable(actor, assistant_id)
        next_no = await self.session.scalar(
            select(func.coalesce(func.max(AssistantVersion.version_no), 0) + 1)
            .where(AssistantVersion.assistant_id == assistant.id)
        )
        row = AssistantVersion(
            assistant_id=assistant.id, version_no=next_no,
            status=AssistantVersionStatus.DRAFT, created_by_user_id=actor.id, **fields,
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="assistant.version.create",
            target_type="assistant_version", target_id=str(row.id),
            detail={"assistant_id": str(assistant.id), "version_no": next_no},
        )
        await self.session.commit()
        return row

    async def update_version(
        self, *, actor: User, assistant_id: uuid.UUID, version_id: uuid.UUID, **fields
    ) -> AssistantVersion:
        version = await self._draft(actor, assistant_id, version_id)
        for key, value in fields.items():
            if value is not None:
                setattr(version, key, value)
        await self.session.commit()
        return version

    async def publish_version(
        self, *, actor: User, assistant_id: uuid.UUID, version_id: uuid.UUID
    ) -> Assistant:
        """Point the assistant at this version. Publishing an older version is the rollback.

        Admin-only. A version decides which tools a model may reach, so promoting one is a
        privilege change — the same reason approving a higher-tier remediation is not a
        technician's call.
        """
        if actor.role is not UserRole.ADMIN:
            raise ValidationError("Only an admin can publish an assistant version")

        assistant = await self._writable(actor, assistant_id)
        version = await self.session.get(AssistantVersion, version_id)
        if version is None or version.assistant_id != assistant.id:
            raise NotFoundError("Version not found")
        if version.status is AssistantVersionStatus.ARCHIVED:
            raise ValidationError("Archived versions cannot be published")

        previous = assistant.published_version_id
        version.status = AssistantVersionStatus.PUBLISHED
        assistant.published_version_id = version.id
        await self.session.flush()
        await self.audit.record(
            org_id=actor.org_id, actor_id=actor.id, action="assistant.publish",
            target_type="assistant", target_id=str(assistant.id),
            detail={
                "version_id": str(version.id), "version_no": version.version_no,
                "previous_version_id": str(previous) if previous else None,
            },
        )
        await self.session.commit()
        return assistant

    # ── Guards ─────────────────────────────────────────────────────────────
    async def _writable(self, actor: User, assistant_id: uuid.UUID) -> Assistant:
        row = await self.get(org_id=actor.org_id, assistant_id=assistant_id)
        if row.org_id is None:
            raise ValidationError(
                "Built-in assistants cannot be edited. Create your own to change its behaviour."
            )
        return row

    async def _draft(
        self, actor: User, assistant_id: uuid.UUID, version_id: uuid.UUID
    ) -> AssistantVersion:
        assistant = await self._writable(actor, assistant_id)
        version = await self.session.get(AssistantVersion, version_id)
        if version is None or version.assistant_id != assistant.id:
            raise NotFoundError("Version not found")
        if version.status is not AssistantVersionStatus.DRAFT:
            raise ValidationError(
                "Published versions are immutable. Create a new draft to change behaviour."
            )
        return version
