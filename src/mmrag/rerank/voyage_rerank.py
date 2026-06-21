"""Cross-encoder reranking via Voyage rerank-2.5.

Reorders the fused candidate set by query-document relevance and keeps the
top-n. Returns ``None`` from the factory when no Voyage key is configured, so
the retriever falls back to RRF order.
"""

from __future__ import annotations

from ..config import CONFIG
from ..store.hybrid import RetrievalResult


class VoyageReranker:
    def __init__(self) -> None:
        import voyageai

        self._client = voyageai.Client(api_key=CONFIG.voyage_api_key)
        self._model = CONFIG.rerank_model

    def rerank(
        self, query: str, results: list[RetrievalResult], top_n: int
    ) -> list[RetrievalResult]:
        if not results:
            return results
        docs = [r.chunk.text for r in results]
        resp = self._client.rerank(query, docs, model=self._model, top_k=top_n)
        out: list[RetrievalResult] = []
        for item in resp.results:
            r = results[item.index]
            out.append(RetrievalResult(r.chunk, float(item.relevance_score), r.sources))
        return out


def get_reranker():
    if CONFIG.use_voyage:
        return VoyageReranker()
    return None
