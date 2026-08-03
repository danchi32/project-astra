"""Turning confirmed fixes into knowledge.

The knowledge base could only ever contain what someone sat down and typed. Meanwhile the
platform resolves the same handful of problems dozens of times a week and remembers none of
it — the evidence that a fix works is thrown away the moment the task row is written.

This module closes that loop. Three rules shape it, and all three exist to stop the base
filling with confident noise:

  1. A learned article needs REPEATED confirmation. One success is an anecdote; publishing
     it would bury hand-written runbooks under a stream of near-identical entries.
  2. It records failures too, and stops recommending a fix whose success rate collapses.
     A fix that worked eleven times and has now failed four is exactly the article that
     would otherwise keep being handed to the assistant as settled truth.
  3. It keeps the user's own words. Retrieval matches what a person types, not what a
     technical writer would have called the problem.
"""
import re
from datetime import datetime

from app.models import KnowledgeArticle
from app.models.base import utcnow

# Confirmations before a candidate becomes searchable. Three is the smallest number that
# distinguishes a pattern from a coincidence, and low enough that a busy org sees learning
# happen within its first week rather than its first quarter.
PUBLISH_AFTER = 3

# Enough attempts to judge by, and the rate below which the fix stops being advice. Both
# apply only AFTER publication — a candidate that has not earned its place is simply not
# recommended in the first place.
MIN_ATTEMPTS_TO_JUDGE = 5
MIN_SUCCESS_RATE = 0.6

# How many distinct user phrasings an article carries. Each one widens what the article
# matches; past a handful they stop adding vocabulary and start diluting the embedding.
MAX_SAMPLES = 6

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Anything that looks like an account, ticket, phone or card number. A symptom is worth
# keeping; the identifier a user pasted alongside it is not, and this text becomes readable
# by everyone in the organization.
_LONG_DIGITS_RE = re.compile(r"\b\d[\d\s-]{5,}\d\b")
_UNC_PATH_RE = re.compile(r"\\\\[^\s]+")


def redact(text: str) -> str:
    """Strip the identifiers people paste into a chat before the words become an article."""
    text = _EMAIL_RE.sub("[email]", text)
    text = _UNC_PATH_RE.sub("[path]", text)
    text = _LONG_DIGITS_RE.sub("[number]", text)
    return " ".join(text.split())


def topic_key(action_id: str, params: dict | None) -> str:
    """The identity of a learned article.

    Actions that name a target need that target in the key: "restart an application" is
    not one runbook, it is one runbook per application. Everything else keys on the action
    alone, which is what makes learning converge quickly enough to be useful — the symptom
    wording varies endlessly, the fix that resolved it does not.
    """
    target = None
    for field in ("process_name", "service_name", "adapter_name", "username"):
        value = (params or {}).get(field)
        if isinstance(value, str) and value.strip():
            target = value.strip().lower()
            break
    key = action_id if target is None else f"{action_id}:{target}"
    return key[:50]


def is_recommendable(article: KnowledgeArticle) -> bool:
    """Whether a published learned article still deserves to be handed to the assistant."""
    attempts = article.successes + article.failures
    if attempts < MIN_ATTEMPTS_TO_JUDGE:
        return True
    return article.successes / attempts >= MIN_SUCCESS_RATE


def render(*, action_label: str, samples: list[str], successes: int, failures: int,
           last_seen: datetime) -> tuple[str, str]:
    """Build the article body. Returns (title, content).

    Written for the two readers it actually has: a technician skimming the knowledge page,
    and the retrieval step, which only sees this text. Hence the plain headings and the
    verbatim user phrasings — and hence the evidence line, so nobody has to take the
    article's word for it.
    """
    first = samples[0] if samples else action_label
    title = f"{first[:120]} — {action_label}"

    lines = [f"**Fix:** {action_label}", "", "**Reported by users as:**"]
    lines += [f"- \"{s}\"" for s in samples]
    attempts = successes + failures
    lines += [
        "",
        f"**Evidence:** applied {attempts} time{'' if attempts == 1 else 's'}, "
        f"{successes} succeeded, {failures} failed. "
        f"Last confirmed {last_seen.date().isoformat()}.",
        "",
        "_Learned automatically from fixes that resolved this on real devices._",
    ]
    return title, "\n".join(lines)
