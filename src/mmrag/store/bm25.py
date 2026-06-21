"""BM25 keyword index.

Strong exactly where dense retrieval is weak: exact identifiers, codes, and
product names. Tokenization keeps alphanumerics and hyphens together so an id
like ``LFE5U-25F`` stays one token.

Persisted to disk as a pickle so ingestion and the API process can share it.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from ..schema import Chunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _flatten_meta(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for v in metadata.values():
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        else:
            parts.append(str(v))
    return " ".join(parts)


class BM25Index:
    def __init__(self) -> None:
        self._bm25 = None
        self._chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk]) -> None:
        from rank_bm25 import BM25Okapi

        self._chunks = chunks
        # Index text plus flattened metadata values (codes, product ids, …) so
        # exact identifiers stay reliably matchable.
        corpus = [_tokenize(c.text + " " + _flatten_meta(c.metadata)) for c in chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]
        return [(self._chunks[i], float(scores[i])) for i in ranked if scores[i] > 0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {"bm25": self._bm25, "chunks": [c.to_payload() for c in self._chunks]},
                f,
            )

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        idx = cls()
        with open(path, "rb") as f:
            data = pickle.load(f)
        idx._bm25 = data["bm25"]
        idx._chunks = [Chunk.from_payload(p) for p in data["chunks"]]
        return idx
