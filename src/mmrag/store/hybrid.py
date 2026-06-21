"""Hybrid retriever: dense + BM25 → RRF fusion → revision resolution → rerank.

Pipeline per query:
1. Dense search (vector store, metadata-filtered) and BM25 keyword search.
2. Reciprocal Rank Fusion combines the two rankings (rank-based, so the
   incomparable score scales of cosine vs BM25 don't need normalization).
3. Revision-conflict resolution drops chunks from older document revisions when
   a newer revision covers the same (doc_id, doc_type, section), unless the
   caller pinned a specific version.
4. Optional cross-encoder rerank (Voyage) selects the final top-n.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import CONFIG
from ..embed.base import Embedder
from ..schema import Chunk
from .bm25 import BM25Index
from .filters import passes_filter


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    sources: list[str]  # which retrievers surfaced it: {"dense", "bm25"}


class HybridRetriever:
    def __init__(self, vector_store, bm25: BM25Index, embedder: Embedder, reranker=None) -> None:
        self.vs = vector_store
        self.bm25 = bm25
        self.embedder = embedder
        self.reranker = reranker

    def retrieve(
        self,
        query: str,
        filters: dict | None = None,
        top_n: int | None = None,
        pin_version: str | None = None,
    ) -> list[RetrievalResult]:
        top_n = top_n or CONFIG.rerank_top_n

        qvec = self.embedder.embed_query(query)
        dense = self.vs.search(qvec, CONFIG.dense_top_k, filters)
        bm = self.bm25.search(query, CONFIG.bm25_top_k)
        # rank-bm25 can't filter; apply the same metadata filter post-hoc.
        bm = [(c, s) for c, s in bm if passes_filter(c, filters)]

        fused = _rrf_fuse(dense, bm, CONFIG.rrf_k)

        if CONFIG.prefer_latest_revision:
            fused = _resolve_revisions(fused, pin_version)

        results = [RetrievalResult(c, s, src) for c, s, src in fused]

        if self.reranker is not None and results:
            results = self.reranker.rerank(query, results, top_n)
        else:
            results = results[:top_n]
        return results


def _rrf_fuse(
    dense: list[tuple[Chunk, float]],
    bm: list[tuple[Chunk, float]],
    k: int,
) -> list[tuple[Chunk, float, list[str]]]:
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}
    sources: dict[str, set[str]] = {}

    for label, ranking in (("dense", dense), ("bm25", bm)):
        for rank, (chunk, _) in enumerate(ranking):
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            chunks[cid] = chunk
            sources.setdefault(cid, set()).add(label)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(chunks[cid], score, sorted(sources[cid])) for cid, score in ordered]


def _resolve_revisions(
    fused: list[tuple[Chunk, float, list[str]]],
    pin_version: str | None,
) -> list[tuple[Chunk, float, list[str]]]:
    """Keep only the newest revision per (doc_id, doc_type, section).

    When ``pin_version`` is set, that version is preferred and others in its
    group are dropped, honoring an explicit user request for a specific rev.
    """
    newest: dict[tuple, tuple[str, str]] = {}  # group -> (version_date, version)
    for chunk, _, _ in fused:
        key = (chunk.doc_id, chunk.doc_type, chunk.section_number)
        cur = newest.get(key)
        if cur is None or chunk.version_date > cur[0]:
            newest[key] = (chunk.version_date, chunk.version)

    out: list[tuple[Chunk, float, list[str]]] = []
    for chunk, score, src in fused:
        key = (chunk.doc_id, chunk.doc_type, chunk.section_number)
        target_date, target_version = newest[key]
        if pin_version:
            if chunk.version == pin_version:
                out.append((chunk, score, src))
            continue
        if chunk.version_date == target_date:
            out.append((chunk, score, src))
        else:
            chunk.superseded_by = target_version
    return out
