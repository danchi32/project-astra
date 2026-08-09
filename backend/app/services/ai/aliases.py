"""Generating the words a user would actually type for a runbook.

Retrieval matches words. Technicians write "High memory utilization troubleshooting";
employees type "mera laptop bahut slow hai". Those two share nothing, so the article the
person needs is the one they cannot find.

Learning already closes half of this: a learned article carries the real phrasings that
preceded a confirmed fix. This closes the other half — when a human writes an article, ask
the model once what a non-technical user would call the problem, and store those phrasings
alongside it so the search has something to match on.

Two properties make this cheap enough to be worth it:

  - **Once per article, not once per search.** Articles are written rarely and searched
    constantly, so the cost sits on the rare side.
  - **Inert without a key.** No Anthropic key means no aliases and no error — retrieval
    behaves exactly as it does today. Same posture as email, billing and embeddings.

This is not semantic understanding. It is pre-computed vocabulary, and a phrasing nobody
predicted still misses. But it is the difference between a knowledge base that answers the
questions people ask and one that only answers the questions technicians would ask.
"""
import json
import logging
import re

from app.core.config import get_settings
from app.services.ai.provider import LLMProvider, get_provider

logger = logging.getLogger(__name__)

# Enough to cover the common ways one problem gets described without turning the article
# into a keyword dump — past this they stop adding vocabulary and start diluting it.
MAX_ALIASES = 8
MAX_ALIAS_CHARS = 120

_PROMPT = """\
You are helping an IT knowledge base be findable by the people who need it.

Below is an article written by an IT technician. Write the short phrases a NON-TECHNICAL \
employee would actually type into a support chat when they have this problem.

Rules:
- Write how a frustrated employee types: lowercase, short, often not a full sentence.
- Use the SYMPTOM they notice, never the technical cause. They do not know the cause.
- Many of these users write Hinglish (Hindi in Latin script). Include a few, e.g. \
"laptop bahut slow hai", "outlook khul nahi raha".
- Vary the wording. Do not restate the article's own title in different word order.
- If the article is not about a user-visible problem (a policy, a process, a reference \
document), return an empty list.

Return ONLY a JSON array of strings. No prose, no code fence.

Article title: {title}

Article body:
{content}
"""


class AliasGenerator:
    """Produces user-phrasings for an article. Never raises."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider
        # Whether a real model is configured. Without one there is nothing useful to ask:
        # the stub provider answers device-support questions, not this.
        self._enabled = provider is not None or bool(get_settings().anthropic_api_key)

    async def for_article(self, *, title: str, content: str) -> list[str] | None:
        """Aliases for one article.

        Three outcomes, and the caller must be able to tell them apart:

          ``["wifi keeps dropping", ...]``  the model answered
          ``[]``                            the model answered with nothing useful
          ``None``                          we never got to ask — no key, or the call failed

        Never raises. An article with no aliases is merely findable by fewer words; an
        article that could not be saved because the model was busy is a technician's work
        thrown away. But the difference between "asked and got nothing" and "never asked"
        is what makes the second one fixable later, so it is not flattened into [].
        """
        if not self._enabled:
            return None

        provider = self._provider or get_provider()
        prompt = _PROMPT.format(title=title[:300], content=content[:4000])

        try:
            response = await provider.generate(
                system="You produce only JSON. No explanation.",
                messages=[{"role": "user", "content": prompt}],
                tools=[],
            )
        except Exception:  # noqa: BLE001 — an article must save even if the model is down
            logger.warning("Alias generation failed for %r; saving without aliases", title[:60])
            return None

        return _parse(response.text)


def _parse(text: str) -> list[str]:
    """Pull a list of phrases out of the model's reply.

    Tolerant on purpose: models wrap JSON in fences or add a sentence before it, and losing
    every alias to a stray backtick would be a silly way to lose the feature.
    """
    if not text:
        return []

    candidate = text.strip()
    # Strip a ```json fence if present.
    fence = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    # Otherwise take the outermost [...] so a leading sentence doesn't break parsing.
    elif not candidate.startswith("["):
        bracket = re.search(r"\[.*\]", candidate, re.DOTALL)
        if not bracket:
            return []
        candidate = bracket.group(0)

    try:
        parsed = json.loads(candidate)
    except ValueError:
        return []
    if not isinstance(parsed, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        phrase = " ".join(item.split())[:MAX_ALIAS_CHARS].strip()
        key = phrase.lower()
        if not phrase or key in seen:
            continue
        seen.add(key)
        out.append(phrase)
        if len(out) >= MAX_ALIASES:
            break
    return out


def embedding_text(title: str, content: str, aliases: list[str] | None) -> str:
    """What gets embedded — the article plus the words people use for it.

    Deliberately different from what is displayed. The aliases exist to be matched against,
    not read: showing a technician's runbook with eight paraphrases of "it's broken"
    stapled underneath would make the article worse to read while making it easier to find.
    """
    parts = [title, content]
    if aliases:
        parts.extend(aliases)
    return "\n".join(parts)
