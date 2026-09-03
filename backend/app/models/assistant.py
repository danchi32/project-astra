"""Configurable AI assistants — the persona the cognitive engine runs as.

Named "assistant" rather than "agent" deliberately. In this codebase "agent" already means
the Windows service on the device (`api/v1/agent.py`, `agent_enrollment_key`,
`AstraAgent.Service`), and reusing the word for the AI persona would make every future
reference ambiguous. The product may still call these Agents to customers.

Two tables rather than one, for the same reason `approved_version_id` points at a version
elsewhere in this codebase: editing a prompt must not change what is already live. Drafts
are edited freely; publishing is a separate, audited act that moves a pointer; rolling back
is publishing an older version again.

Every behaviour column is NULLABLE, and NULL means "use the server default". That is what
makes this table safe to add to a running system: a row full of NULLs behaves exactly as
ASTRA does today, so the engine can start reading rows without any behaviour changing.
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class AssistantVersionStatus(str, enum.Enum):
    DRAFT = "draft"          # editable; never served
    PUBLISHED = "published"  # immutable; may be pointed at by assistants.published_version_id
    ARCHIVED = "archived"    # was published once; kept so a trace can still name it


class Assistant(TimestampMixin, Base):
    """An AI persona an organization can run. Identity only — behaviour lives on versions."""

    __tablename__ = "assistants"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    # NULL org_id = a BUILT-IN assistant owned by the platform operator and visible to every
    # organization — the same convention `knowledge_articles` already uses for global
    # articles. The current ASTRA System Administrator persona is seeded this way, which is
    # why tenants must not be able to edit or delete a NULL-org row.
    org_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The version currently served. NULL means the assistant exists but has never been
    # published — it is a draft nobody can run yet, which is the correct state for a
    # half-configured assistant and the reason this is a pointer rather than a status flag
    # on the version: "which words did a human approve" is a question only a pointer answers.
    #
    # No FK constraint, because assistant_versions.assistant_id already points back here and
    # a circular constraint costs more ceremony than it buys. `audit_logs.actor_id` and the
    # billing id columns are unconstrained GUIDs for the same reason.
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class AssistantVersion(TimestampMixin, Base):
    """One immutable-once-published configuration of an assistant."""

    __tablename__ = "assistant_versions"
    __table_args__ = (
        UniqueConstraint("assistant_id", "version_no", name="uq_assistant_versions_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    assistant_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Monotonic per assistant, allocated server-side. Humans refer to "v3", not to a UUID,
    # and a trace that says "ran v3" has to survive the row being archived.
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[AssistantVersionStatus] = mapped_column(
        Enum(AssistantVersionStatus, native_enum=False, length=20,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AssistantVersionStatus.DRAFT,
        index=True,
    )

    # ── Behaviour. Every column below is NULL-means-server-default. ────────
    #
    # The brief sent to a real model. NULL keeps today's constant, which is what lets the
    # built-in assistant be seeded before the engine reads any of this.
    #
    # Only ONE prompt is stored even though `cognitive.py` chooses between two today. The
    # second one goes to the built-in rule providers, and those ignore a system prompt
    # entirely — modelling text nobody reads would be modelling a no-op.
    system_prompt: Mapped[str | None] = mapped_column(String(20000), nullable=True)

    # NULL → settings.ai_model / ai_max_tokens / ai_max_tool_iterations.
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_tool_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tool names this version may call. NULL → every tool the engine advertises today, so a
    # seeded row is not a restriction. An empty list is NOT the same as NULL: it means this
    # assistant may call nothing, which is a legitimate configuration (answer-only).
    #
    # Grants are a filter, never a grant of privilege: the tier and operator_only rules in
    # the remediation registry still apply on top, and an id listed here that the registry
    # withholds stays withheld.
    tool_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    # Free-form notes from whoever published it, shown in the version list.
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def resolved(self, *, defaults: dict[str, Any]) -> dict[str, Any]:
        """This version's settings with NULLs filled from server defaults.

        One place decides what NULL means, so the engine never re-derives it and a test can
        assert the fallback without going through a model call.

        `model` and `max_tokens` are absent on purpose: the engine does not build the
        provider — `ConversationService._route` does, choosing between the free built-in
        paths and the real LLM on cost. Honouring a per-version model means threading the
        version through that decision, which is its own change. Until then the API refuses a
        non-NULL value rather than accepting one and ignoring it.
        """
        ceiling = defaults["max_tool_iterations"]
        return {
            "system_prompt": self.system_prompt or defaults["system_prompt"],
            # A version may LOWER the iteration cap, never raise it. Each iteration is a
            # billed model call, so a raisable cap is a tenant-writable multiplier on the
            # AI bill — the one cost lever this table would otherwise hand out.
            #
            # The API refuses a value above the server setting, so reaching this clamp means
            # a row got written another way (a seed script, a migration, a fixture). Both
            # layers on purpose: the same defence in depth as the backend action registry
            # and the agent's own hardcoded allowlist.
            "max_tool_iterations": min(self.max_tool_iterations or ceiling, ceiling),
            "tool_ids": self.tool_ids,  # None stays None — "all tools", not a default value
        }
