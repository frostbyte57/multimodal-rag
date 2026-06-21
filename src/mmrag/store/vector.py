"""Vector store: factory + in-memory backend.

``get_vector_store()`` returns the pgvector-backed store in production
(``DATABASE_URL``) or an in-memory store when ``VECTOR_IN_MEMORY=1`` (tests, CI,
zero-setup demo). Both expose the same interface:

    recreate(dim)                -> reset/create storage for ``dim``-d vectors
    upsert(chunks, vectors)      -> add chunks with their embeddings
    search(qvec, top_k, filters) -> [(Chunk, score)] by cosine similarity
"""

from __future__ import annotations

import math

from ..config import CONFIG
from ..schema import Chunk
from .filters import passes_filter


class InMemoryVectorStore:
    """Pure-Python cosine-similarity store. No external services."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def recreate(self, dim: int) -> None:  # noqa: ARG002 - dim irrelevant here
        self._chunks = []
        self._vectors = []

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        self._chunks.extend(chunks)
        self._vectors.extend(vectors)

    def search(
        self, query_vec: list[float], top_k: int, filters: dict | None = None
    ) -> list[tuple[Chunk, float]]:
        qn = math.sqrt(sum(v * v for v in query_vec)) or 1.0
        scored: list[tuple[Chunk, float]] = []
        for chunk, vec in zip(self._chunks, self._vectors):
            if not passes_filter(chunk, filters):
                continue
            dot = sum(a * b for a, b in zip(query_vec, vec))
            vn = math.sqrt(sum(v * v for v in vec)) or 1.0
            scored.append((chunk, dot / (qn * vn)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def get_vector_store():
    if CONFIG.vector_in_memory:
        return InMemoryVectorStore()
    from .pg import PgVectorStore

    return PgVectorStore()
