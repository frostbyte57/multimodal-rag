"""Construct a ready-to-query :class:`HybridRetriever`.

Two construction paths:

* ``load_retriever`` — connect to already-populated persistent stores
  (Postgres/pgvector + on-disk BM25). Use after running ``scripts/ingest.py``.
* ``build_in_memory_retriever`` — ingest a corpus into in-memory stores within
  this process and return a retriever bound to them. Used for tests, the eval
  harness, and the zero-setup demo, where persistent state can't be shared
  across processes.
"""

from __future__ import annotations

from pathlib import Path

from .config import CONFIG
from .embed.base import get_embedder
from .ingest.chunk import chunk_document
from .ingest.parse import parse_file
from .ingest.pipeline import discover
from .rerank.voyage_rerank import get_reranker
from .schema import Chunk
from .store.bm25 import BM25Index
from .store.hybrid import HybridRetriever
from .store.vector import InMemoryVectorStore, get_vector_store


def load_retriever() -> HybridRetriever:
    embedder = get_embedder()
    vs = get_vector_store()
    bm25 = BM25Index.load(CONFIG.bm25_index_path)
    from .store.graph import GraphStore
    graph = GraphStore.load(CONFIG.graph_index_path)
    return HybridRetriever(vs, bm25, embedder, reranker=get_reranker(), graph=graph)


def build_in_memory_retriever(
    corpus_dir: Path | None = None,
) -> tuple[HybridRetriever, list[Chunk]]:
    corpus_dir = corpus_dir or CONFIG.corpus_dir
    chunks: list[Chunk] = []
    for path in discover(corpus_dir):
        chunks.extend(chunk_document(parse_file(path)))
    if not chunks:
        raise RuntimeError(f"No chunks produced from {corpus_dir}")

    embedder = get_embedder()
    vectors = embedder.embed_chunks(chunks)

    vs = InMemoryVectorStore()  # always in-memory regardless of config
    vs.recreate(dim=embedder.dim)
    vs.upsert(chunks, vectors)

    bm25 = BM25Index()
    bm25.build(chunks)

    from .store.graph import GraphStore
    from .ingest.graph import extract_triplets
    graph = GraphStore()
    if CONFIG.use_graphrag:
        for chunk in chunks:
            triplets = extract_triplets(chunk)
            if triplets:
                graph.add_triplets(triplets)

    return HybridRetriever(vs, bm25, embedder, reranker=get_reranker(), graph=graph), chunks
