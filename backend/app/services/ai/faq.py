"""Built-in question-and-answer knowledge, and how it is retrieved.

Two corpora sit on top of this module — `public_faq` for the website, `portal_faq` for
signed-in users — and they share the machinery here rather than each growing their own.

Retrieval is lexical: word overlap between the question and the entry, with the curated
keywords weighted above the prose. That is a deliberate choice, not a stopgap. These
corpora are small and their wording is ours, so overlap is predictable and free, where an
embedding call would add a network round trip to every message somebody types. It also
keeps working when nothing else does: no API key, no model, no network — the assistants
still answer, because the answers are already written.
"""
import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from app.services.ai.embeddings import normalise


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str
    #: Words somebody might use that appear in neither the question nor the answer.
    #: Without them "cost" scores zero against an entry that only ever says "priced".
    #:
    #: Routing signals, not decoration: keep them topical. A question word ("how",
    #: "which", "much") routes nothing, and weighted as heavily as these are, one stray
    #: "how" was enough to pull "how do I buy" onto an entry about the reasoning loop.
    keywords: tuple[str, ...] = ()

    def prose(self) -> str:
        """What the entry actually says."""
        return f"{self.question} {self.answer}"

    def routing(self) -> str:
        """The words that mean 'this entry, not its neighbour'."""
        return " ".join(self.keywords)


#: How much of the question an entry has to account for before it counts as an answer.
#: Weighted by rarity, so this reads as "most of what was distinctive about the question",
#: not "a third of its words". Calibrated against a set of real questions and a set of
#: things nobody should get an answer to — see tests/test_support_bot.py.
MIN_SCORE = 0.4

#: How much a keyword hit outweighs a prose hit WHEN RANKING entries that already qualify.
#: Keywords are the curated statement of what an entry is FOR, while prose overlap is an
#: accident of vocabulary — "employee" appears in half these answers, but only one of them
#: is about employee monitoring.
ROUTING_WEIGHT = 2.0


@lru_cache(maxsize=8)
def _document_frequency(corpus: tuple[FaqEntry, ...]) -> tuple[int, Counter]:
    """How many entries each word appears in. Computed once per corpus."""
    frequency: Counter = Counter()
    for entry in corpus:
        frequency.update(set(normalise(entry.prose())) | set(normalise(entry.routing())))
    return len(corpus), frequency


def _weight(token: str, total: int, frequency: Counter) -> float:
    """How much matching this word should count for.

    Plain overlap counted every word the same, and these corpora are lists of questions:
    "how" appears in a third of them, "ASTRA" in nearly all. So "how do I claim expenses"
    — a question about nothing in the corpus — matched three entries on the strength of
    "how" alone and was served as an answer. Rarity is what carries meaning here, so it
    is what carries weight. A word the corpus has never seen scores highest of all, which
    matters in the denominator: a question made of unknown words should score low, not be
    excused for having nothing to match.
    """
    return math.log((total + 1) / (frequency.get(token, 0) + 1)) + 1.0


def search(corpus: tuple[FaqEntry, ...], query: str, *, limit: int = 4) -> list[FaqEntry]:
    """The entries a question is actually about, best first.

    Scored by how much of the *question* is covered, not how much of the entry: a long
    answer must not be penalised for containing words the asker did not type. Order
    matters beyond the model's benefit — with no model reachable, the top entry IS the
    answer somebody reads.
    """
    wanted = set(normalise(query))
    if not wanted:
        return []

    total, frequency = _document_frequency(corpus)
    weights = {token: _weight(token, total, frequency) for token in wanted}
    asked = sum(weights.values())

    scored: list[tuple[float, int, FaqEntry]] = []
    for index, entry in enumerate(corpus):
        prose = wanted & set(normalise(entry.prose()))
        routing = wanted & set(normalise(entry.routing()))
        matched = prose | routing

        # Two different questions, deliberately kept apart. Coverage — how much of what
        # was asked this entry accounts for — decides WHETHER it is about the question at
        # all. The keyword bonus only decides WHICH of the entries that pass is best.
        # Folded together, one rare keyword could carry an entry over the bar on its own:
        # "write a poem about the sea" matched the knowledge-base entry, because it lists
        # "write", and two words the corpus had never seen counted for nothing against it.
        coverage = sum(weights[token] for token in matched) / asked
        if coverage < MIN_SCORE:
            continue
        rank = coverage + (ROUTING_WEIGHT - 1.0) * (
            sum(weights[token] for token in routing) / asked
        )
        # `index` keeps the sort total and stable — FaqEntry is not orderable, so two
        # entries tying on score would otherwise raise rather than pick one.
        scored.append((rank, index, entry))

    scored.sort(key=lambda triple: (-triple[0], triple[1]))
    return [entry for _, _, entry in scored[:limit]]
