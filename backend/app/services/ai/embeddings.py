"""Embedding providers for the knowledge base, the semantic cache, and learned actions.

Two things about this module matter more than the provider implementations.

**Every stored vector carries the name of the provider that produced it.** Vectors from
different models are not comparable — cosine similarity between a 256-dim hash vector and a
1024-dim Voyage vector isn't "low", it's meaningless. Because `cosine_similarity` returns
0.0 on a length mismatch, mixing them produces no error and no warning: every older article
silently stops being found, and the knowledge base looks empty rather than broken. The
`name` on each provider is what lets a search filter to its own vector space, and what lets
a backfill find the rows that still need re-embedding.

**Indexing and searching are different operations.** Retrieval models are asymmetric: a
document is embedded to be *found*, a query to *find*. Passing the wrong one costs accuracy
silently, so `embed()` takes the purpose as a required argument rather than defaulting.
"""
import asyncio
import hashlib
import logging
import math
import re
from typing import Literal, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

Purpose = Literal["document", "query"]

# The name recorded on rows written before providers were named. Every vector in the
# database at that point came from the 256-dimension hashing provider.
LEGACY_MODEL = "hash-256"


class EmbeddingError(RuntimeError):
    """The provider could not produce a vector.

    Deliberately not caught here. Storing a row without a usable vector makes it
    permanently unfindable, and returning an empty search result would report "nothing in
    the knowledge base" when the truth is "the embedding service is down" — the difference
    matters to whoever is looking at the screen.
    """


class EmbeddingProvider(Protocol):
    """A vector space. `name` identifies it; vectors are only comparable within one."""

    name: str

    async def embed(self, text: str, *, purpose: Purpose) -> list[float]: ...


class HashingEmbeddingProvider:
    """Deterministic, dependency-free embeddings via signed feature hashing of tokens.

    Matches on shared words, not on meaning: "printer not printing" and "spooler service
    stopped" score zero against each other despite describing one problem. That is the
    ceiling of this approach, and the reason a real model is worth configuring — but it
    needs no key, no network and no cost, so it keeps local demos, tests and unconfigured
    installs working instead of failing.

    `purpose` is ignored: there is no asymmetry to exploit in a bag of hashed tokens.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    async def embed(self, text: str, *, purpose: Purpose) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = digest % self.dim
            sign = 1.0 if (digest >> 8) & 1 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class VoyageEmbeddingProvider:
    """Voyage AI embeddings — https://docs.voyageai.com/reference/embeddings-api

    Anthropic does not offer an embeddings endpoint and recommends Voyage, which is why
    this is the hosted option rather than something Claude-shaped.

    The model id is part of `name`: switching models is switching vector spaces, and the
    stored rows have to say which one they came from.
    """

    _URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str, *, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self.model = model
        self.name = f"voyage:{model}"
        self._timeout = timeout

    async def embed(self, text: str, *, purpose: Purpose) -> list[float]:
        payload = {
            "input": [text],
            "model": self.model,
            # Voyage prepends a different instruction for each: a document is embedded to
            # be found, a query to find. Sending "document" for both is the most common way
            # to quietly lose retrieval accuracy.
            "input_type": purpose,
            # Long runbooks are worth truncating rather than failing — a partial embedding
            # of a 40k-character article still retrieves it.
            "truncation": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingError(f"Voyage embedding request failed: {exc}") from exc

        # Response: {"data": [{"embedding": [...], "index": 0}], ...}. Ordering is not
        # promised — that is what `index` is for — so sort rather than assume.
        rows = body.get("data") or []
        if not rows:
            raise EmbeddingError("Voyage returned no embeddings")
        rows.sort(key=lambda r: r.get("index", 0))
        vector = rows[0].get("embedding")
        if not vector:
            raise EmbeddingError("Voyage returned an empty embedding")
        return [float(v) for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Both vectors must come from the same provider — see the module docstring.

    Returns 0.0 rather than raising on a mismatch, which is why callers filter by
    `embedding_model` BEFORE scoring instead of relying on this to notice.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """The configured provider, or the offline default.

    Cached: constructing a provider is cheap, but every service builds one per request and
    a shared instance keeps the name stable across them.
    """
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_embedding_provider() -> None:
    """Drop the cached provider. For tests that change configuration."""
    global _provider
    _provider = None


def _build_provider() -> EmbeddingProvider:
    settings = get_settings()
    choice = (settings.embedding_provider or "auto").lower()

    if choice in ("auto", "voyage") and settings.voyage_api_key:
        return VoyageEmbeddingProvider(settings.voyage_api_key, settings.voyage_model)

    if choice == "voyage":
        # Asked for explicitly and not usable. Falling back would write hash vectors into
        # a base the operator believes is running a real model, and the two are silently
        # incompatible — better to refuse at startup than to corrupt the store.
        raise EmbeddingError(
            "ASTRA_EMBEDDING_PROVIDER=voyage but ASTRA_VOYAGE_API_KEY is not set"
        )

    return HashingEmbeddingProvider()


async def embed_many(
    provider: EmbeddingProvider, texts: list[str], *, purpose: Purpose,
    concurrency: int = 4,
) -> list[list[float]]:
    """Embed a batch, bounded. Used by the re-embed backfill, where the alternative is
    either one request at a time across thousands of rows or an unbounded fan-out at a
    rate-limited API."""
    sem = asyncio.Semaphore(concurrency)

    async def one(text: str) -> list[float]:
        async with sem:
            return await provider.embed(text, purpose=purpose)

    return list(await asyncio.gather(*(one(t) for t in texts)))
