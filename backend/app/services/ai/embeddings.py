"""Embedding provider abstraction for the semantic cache.

Same pattern as the LLM provider: a deterministic offline default so the platform
works with no external service, and a slot for a real embedding model (a local
sentence-transformer, or a hosted embeddings API) in production.
"""
import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class HashingEmbeddingProvider:
    """Deterministic, dependency-free embeddings via signed feature hashing of tokens.

    Not semantically deep, but similar text (shared words) yields high cosine
    similarity — enough to detect repeated / near-duplicate questions offline.
    A real model can replace this behind the same interface.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
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


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def get_embedding_provider() -> EmbeddingProvider:
    # A real embeddings provider would be selected here when configured.
    return HashingEmbeddingProvider()
