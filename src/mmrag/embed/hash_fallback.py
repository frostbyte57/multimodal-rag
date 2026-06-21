"""Deterministic, dependency-free embedder for offline use.

A hashed bag-of-words projected onto a fixed-dim unit sphere. It is NOT
semantically strong — it captures lexical overlap only — but it makes the entire
pipeline (ingest → index → retrieve → eval retrieval recall) runnable with no
API keys or network, which is essential for CI and local development. In the
hybrid retriever it pairs with BM25, so lexical signal is still useful.
"""

from __future__ import annotations

import hashlib
import math
import re

from ..schema import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        # Offline: images are represented by their caption text.
        return [self._vec(c.embedding_text()) for c in chunks]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
