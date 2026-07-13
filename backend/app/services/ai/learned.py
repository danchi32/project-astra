"""Learned-fix store: remembers the remediation the AI applied for an issue the
built-in rules couldn't classify, keyed by the query embedding, so the same kind
of issue is resolved next time by the built-in path with no further LLM call.

Mirrors the semantic cache, but stores an ACTION (action_id + params) rather than
a text answer. This is how the assistant's 'common issue' coverage grows over time.
"""
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import LearnedAction
from app.repositories.learned_actions import LearnedActionRepository
from app.services.ai.embeddings import EmbeddingProvider, cosine_similarity, get_embedding_provider
from app.services.remediation.actions import ACTIONS


class LearnedFix:
    def __init__(self, action_id: str, params: dict[str, Any] | None) -> None:
        self.action_id = action_id
        self.params = params or {}


class LearnedFixStore:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        self.repo = LearnedActionRepository(session)
        self.embed = provider or get_embedding_provider()
        # Applying a fix is more consequential than serving a cached sentence, so
        # require a slightly higher similarity than the text cache.
        self.threshold = max(get_settings().ai_cache_similarity_threshold, 0.88)

    async def lookup(self, *, org_id: uuid.UUID, query: str) -> LearnedFix | None:
        """Return a previously-learned fix for a sufficiently-similar prior issue."""
        query_vec = await self.embed.embed(query)
        best: LearnedAction | None = None
        best_sim = -1.0
        for entry in await self.repo.list_by_org(org_id):
            sim = cosine_similarity(query_vec, entry.embedding)
            if sim > best_sim:
                best_sim, best = sim, entry
        if best is not None and best_sim >= self.threshold:
            best.hit_count += 1
            await self.session.flush()
            return LearnedFix(best.action_id, best.params)
        return None

    async def learn(
        self, *, org_id: uuid.UUID, query: str, action_id: str, params: dict[str, Any] | None
    ) -> None:
        """Remember action_id (+params) as the fix for issues like `query`. No-op for
        an unknown action, or if a near-identical fix is already stored."""
        if action_id not in ACTIONS:
            return
        query_vec = await self.embed.embed(query)
        # Don't pile up duplicates for the same recurring wording + same action.
        for entry in await self.repo.list_by_org(org_id):
            if entry.action_id == action_id and cosine_similarity(query_vec, entry.embedding) >= self.threshold:
                return
        await self.repo.add(
            LearnedAction(
                org_id=org_id,
                query_text=query[:1000],
                embedding=query_vec,
                action_id=action_id,
                params=params or None,
            )
        )


def learnable_action(tool_trail: list[dict[str, Any]] | None) -> tuple[str, dict[str, Any]] | None:
    """Pull the (action_id, params) of a remediation the engine actually created in
    this turn, so it can be learned. Returns None if no task was created."""
    for entry in reversed(tool_trail or []):
        if entry.get("tool") != "propose_remediation":
            continue
        try:
            output = json.loads(entry.get("output") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if "task_id" not in output:  # only learn fixes that were actually applied/queued
            continue
        tool_input = entry.get("input") or {}
        action_id = tool_input.get("action_id")
        if not action_id:
            continue
        params = {k: tool_input[k] for k in ("process_name", "service_name") if tool_input.get(k)}
        return action_id, params
    return None
