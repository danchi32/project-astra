"""Workforce Insights ("Tracker") — AI categorisation of unknown apps/websites.

When a foreground app or domain the built-in taxonomy doesn't know first appears, the model
assigns it one of the built-in categories. The result is written to the GLOBAL learned_categories
store, so the AI is asked once per app/site, ever, across every org. Runs as a best-effort
background pass after activity ingest — never in the response path, never blocking a telemetry
beat, and silent when there is nothing new or no AI key is configured.
"""
import json
import logging
import time
import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.base import utcnow
from app.repositories.workforce import WorkforceRepository
from app.services.ai.provider import get_provider
from app.services.workforce_categories import (
    CATEGORIES,
    PRIVATE_PLACEHOLDER,
    Learned,
    _learned_category,
    category_for,
    category_options,
    registrable_domain,
)

logger = logging.getLogger("astra.workforce.ai")

# Keep each AI call small and bounded — a handful of genuinely new apps/sites per pass.
_MAX_PER_PASS = 12

# This pass is triggered after EVERY activity beat, fleet-wide. Two guards keep that from turning
# into a per-beat database scan and a runaway stream of paid model calls:
#   * a per-org debounce — at most one pass per org per interval, checked before any query, so the
#     thousands of beats a large fleet sends between runs cost nothing. In-memory and best-effort
#     (per process, reset on restart); the back-off below is the durable cost guard.
#   * a negative cache — an item the model can't confidently categorise is marked "pending" and not
#     re-sent until the marker expires, so one stubborn app/site can't be re-billed on every pass.
_MIN_INTERVAL_SECONDS = 300
_RETRY_AFTER = timedelta(days=7)
_last_run: dict[uuid.UUID, float] = {}

_SYSTEM = (
    "You categorise apps and websites for a workplace productivity tracker. For each item you "
    "are given, choose the single best-fitting category from the provided list. Judge by what "
    "the app or site is primarily FOR at work, not by edge cases. Reply with ONLY a JSON object "
    "mapping each item's key to a category key from the list — no prose, no markdown."
)


def _unknown_candidates(
    rows: list[tuple[str | None, str | None]],
    learned: Learned,
    pending: set[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """From raw (app, domain) rows, the distinct items the built-in taxonomy and the learned map
    don't yet cover and that aren't already in the recent "pending" negative cache:
    {(kind, key): a sample label for the prompt}. Domains reduce to the registrable domain so one
    entry covers every subdomain."""
    out: dict[tuple[str, str], str] = {}
    for app, domain in rows:
        if domain and domain != PRIVATE_PLACEHOLDER:
            ident = ("domain", registrable_domain(domain))
            if ident in pending:
                continue
            if category_for(None, domain) == "uncategorised" and _learned_category(None, domain, learned) is None:
                out[ident] = domain
        elif app:
            ident = ("app", app.strip().lower())
            if ident in pending:
                continue
            if category_for(app, None) == "uncategorised" and _learned_category(app, None, learned) is None:
                out[ident] = app
    return out


async def _ask_model(items: dict[tuple[str, str], str]) -> dict[tuple[str, str], str]:
    """Ask the LLM to categorise the items. Returns only entries with a valid category key."""
    options = category_options()
    option_lines = "\n".join(f"- {o['key']}: {o['label']} ({o['bucket']})" for o in options)
    item_lines = "\n".join(
        f'- {{"key": "{key}", "kind": "{kind}", "example": "{sample}"}}'
        for (kind, key), sample in items.items()
    )
    user = (
        f"Categories (choose one key per item):\n{option_lines}\n\n"
        f"Items to categorise:\n{item_lines}\n\n"
        'Reply with JSON like {"<item key>": "<category key>", ...}.'
    )
    resp = await get_provider().generate(
        system=_SYSTEM, messages=[{"role": "user", "content": user}], tools=[])
    text = resp.text.strip()
    # Tolerate a fenced block or stray prose around the object.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        logger.warning("workforce AI classify: no JSON object in response")
        return {}
    try:
        raw = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        logger.warning("workforce AI classify: unparseable JSON")
        return {}

    by_key = {key: (kind, key) for (kind, key) in items}
    out: dict[tuple[str, str], str] = {}
    for key, category in raw.items():
        ident = by_key.get(str(key))
        if ident is not None and category in CATEGORIES and category != "uncategorised":
            out[ident] = category
    return out


async def classify_new_activity(
    session: AsyncSession, org_id: uuid.UUID, *, force: bool = False
) -> int:
    """Best-effort: classify apps/sites newly seen for this org that nothing covers yet, writing
    them to the global store. Returns how many were learned. Safe to call after every beat — it
    debounces per org, skips items in the recent negative cache, and does nothing when there is
    nothing new or no AI key is configured. `force` bypasses the debounce (for tests)."""
    if not get_settings().anthropic_api_key:
        return 0  # no model available — leave unknowns as Neutral rather than guess blindly.

    # Debounce before touching the DB, so the beats between runs cost nothing.
    now = time.monotonic()
    if not force and now - _last_run.get(org_id, float("-inf")) < _MIN_INTERVAL_SECONDS:
        return 0
    _last_run[org_id] = now

    repo = WorkforceRepository(session)
    learned = await repo.learned_map()
    pending = await repo.pending_keys(newer_than=utcnow() - _RETRY_AFTER)
    since = utcnow() - timedelta(days=get_settings().workforce_activity_retention_days)
    rows = await repo.recent_foreground_keys(org_id, since=since, limit=500)

    candidates = _unknown_candidates(rows, learned, pending)
    if not candidates:
        return 0
    batch = dict(list(candidates.items())[:_MAX_PER_PASS])

    decided = await _ask_model(batch)
    for (kind, key), category in decided.items():
        await repo.upsert_learned(kind, key, category, "ai")
    # Negative-cache the items the model couldn't place, so they aren't re-sent every pass. The
    # marker expires after _RETRY_AFTER, so a transient miss is retried eventually.
    unresolved = [ident for ident in batch if ident not in decided]
    for kind, key in unresolved:
        await repo.upsert_learned(kind, key, "uncategorised", "pending")
    if decided or unresolved:
        await session.commit()
    if decided:
        logger.info("workforce AI learned %d new categories for org %s", len(decided), org_id)
    return len(decided)
