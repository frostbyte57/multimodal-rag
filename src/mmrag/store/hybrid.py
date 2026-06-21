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
    def __init__(self, vector_store, bm25: BM25Index, embedder: Embedder, reranker=None, graph=None) -> None:
        self.vs = vector_store
        self.bm25 = bm25
        self.embedder = embedder
        self.reranker = reranker
        self.graph = graph

    def retrieve(
        self,
        query: str,
        filters: dict | None = None,
        top_n: int | None = None,
        pin_version: str | None = None,
        expanded_queries: list[str] | None = None,
    ) -> list[RetrievalResult]:
        top_n = top_n or CONFIG.rerank_top_n

        queries_to_run = expanded_queries if expanded_queries else [query]
        dense: list[tuple[Chunk, float]] = []
        bm: list[tuple[Chunk, float]] = []

        for q in queries_to_run:
            embed_text = q
            if CONFIG.use_hyde:
                from ..agent import generate_hyde_document
                hyde_doc = generate_hyde_document(q)
                if hyde_doc:
                    embed_text = f"{q}\n{hyde_doc}"
                    
            qvec = self.embedder.embed_query(embed_text)
            dense.extend(self.vs.search(qvec, CONFIG.dense_top_k, filters))
            
            # BM25 uses the pure lexical query (HyDE adds noise to exact match)
            bm_res = self.bm25.search(q, CONFIG.bm25_top_k)
            bm.extend([(c, s) for c, s in bm_res if passes_filter(c, filters)])

        # Deduplicate chunks from multiple queries before RRF to prevent ranking bloat
        def _dedupe(ranking: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
            seen = set()
            out = []
            # Sort by score descending to keep the best score for each chunk
            for c, s in sorted(ranking, key=lambda x: x[1], reverse=True):
                if c.chunk_id not in seen:
                    seen.add(c.chunk_id)
                    out.append((c, s))
            return out
            
        dense = _dedupe(dense)
        bm = _dedupe(bm)

        fused = _rrf_fuse(dense, bm, CONFIG.rrf_k)

        if CONFIG.prefer_latest_revision:
            fused = _resolve_revisions(fused, pin_version)

        results = [RetrievalResult(c, s, src) for c, s, src in fused]

        if self.reranker is not None and results:
            results = self.reranker.rerank(query, results, top_n)
        else:
            results = results[:top_n]
            
        if getattr(self, "graph", None) and CONFIG.use_graphrag:
            from ..agent import extract_keywords
            keywords = extract_keywords(query)
            subgraph = self.graph.extract_subgraph(keywords, max_depth=1)
            if subgraph:
                text = "Knowledge Graph Context:\n" + "\n".join(
                    f"- {t.subject} {t.predicate} {t.object}" for t in subgraph
                )
                graph_chunk = Chunk(
                    chunk_id="graph_context",
                    doc_id="Graph",
                    text=text,
                    title="Knowledge Graph",
                    doc_type="graph",
                    version="1",
                    version_date="2099-01-01",
                    section_number="1",
                    section_path=["Graph"],
                    page_start=1,
                    page_end=1,
                    chunk_type="text",
                )
                results.insert(0, RetrievalResult(graph_chunk, score=1.0, sources=["graph"]))
                
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
