"""End-to-end ingestion: discover → parse → chunk → embed → index.

Builds both indexes from a corpus directory. BM25 is persisted to disk; dense
vectors go to Postgres/pgvector (or the in-memory store). Returns the chunks so
callers (e.g. the eval harness) can inspect what was indexed.
"""

from __future__ import annotations

from pathlib import Path

from ..config import CONFIG
from ..embed.base import get_embedder
from ..schema import Chunk
from ..store.bm25 import BM25Index
from ..store.vector import get_vector_store
from .chunk import chunk_document
from .parse import parse_file


def discover(corpus_dir: Path) -> list[Path]:
    files: list[Path] = []
    for ext in ("*.md", "*.markdown", "*.pdf"):
        files.extend(sorted(corpus_dir.glob(ext)))
    return files


def parse_and_chunk(corpus_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in discover(corpus_dir):
        doc = parse_file(path)
        chunks.extend(chunk_document(doc))
    return chunks


def ingest(corpus_dir: Path | None = None, verbose: bool = True) -> list[Chunk]:
    corpus_dir = corpus_dir or CONFIG.corpus_dir
    chunks = parse_and_chunk(corpus_dir)
    if not chunks:
        raise RuntimeError(f"No chunks produced from {corpus_dir}")

    if verbose:
        print(f"Parsed {len(chunks)} chunks from {len(discover(corpus_dir))} documents")

    # BM25
    bm25 = BM25Index()
    bm25.build(chunks)
    bm25.save(CONFIG.bm25_index_path)
    if verbose:
        print(f"Built BM25 index → {CONFIG.bm25_index_path}")

    # Dense (multimodal-aware)
    embedder = get_embedder()
    vectors = embedder.embed_chunks(chunks)
    vs = get_vector_store()
    vs.recreate(dim=embedder.dim)
    vs.upsert(chunks, vectors)
    if verbose:
        backend = "Voyage multimodal" if CONFIG.use_voyage else "hash-fallback (offline)"
        store = "in-memory" if CONFIG.vector_in_memory else f"pgvector ({CONFIG.pg_table})"
        print(f"Embedded with {backend}, upserted to {store}")

    return chunks
