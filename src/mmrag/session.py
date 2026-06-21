"""An interactive RAG session with incremental ingestion.

Unlike the one-shot ``build_in_memory_retriever``, a session can grow: attach a
file or folder at any time and its chunks are parsed, embedded, and added to the
live indexes. Used by the TUI (and usable from a notebook/REPL).

Dense vectors append to the configured vector store (in-memory by default, or
pgvector); BM25 is rebuilt over the full chunk set on each add (cheap for modest
corpora). Already-ingested source files are skipped so re-attaching a folder
doesn't duplicate.
"""

from __future__ import annotations

from pathlib import Path

from .config import CONFIG
from .embed.base import get_embedder
from .generate.answer import AnswerResult, answer_question
from .ingest.chunk import chunk_document
from .ingest.parse import parse_file
from .rerank.voyage_rerank import get_reranker
from .schema import Chunk, ChunkType
from .store.bm25 import BM25Index
from .store.hybrid import HybridRetriever
from .store.vector import get_vector_store

_SUPPORTED = {".md", ".markdown", ".pdf"}


def expand_paths(path: Path) -> list[Path]:
    """Resolve a file or directory into a list of ingestible document paths."""
    path = path.expanduser()
    if path.is_dir():
        out: list[Path] = []
        for ext in ("*.md", "*.markdown", "*.pdf"):
            out.extend(sorted(path.rglob(ext)))
        return out
    if path.is_file() and path.suffix.lower() in _SUPPORTED:
        return [path]
    return []


class RagSession:
    def __init__(self) -> None:
        self.embedder = get_embedder()
        self.reranker = get_reranker()
        self.vs = get_vector_store()
        self.vs.recreate(self.embedder.dim)
        self.bm25 = BM25Index()
        from .store.graph import GraphStore
        self.graph = GraphStore()
        self.chunks: list[Chunk] = []
        self._ingested: set[str] = set()
        self.retriever = HybridRetriever(self.vs, self.bm25, self.embedder, self.reranker, graph=self.graph)

    # -- stats --------------------------------------------------------------
    @property
    def doc_count(self) -> int:
        return len(self._ingested)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def image_count(self) -> int:
        return sum(1 for c in self.chunks if c.chunk_type == ChunkType.IMAGE.value)

    @property
    def backend_label(self) -> str:
        emb = "voyage" if CONFIG.use_voyage else "hash(offline)"
        store = "pgvector"
        gen = CONFIG.generation_model if CONFIG.use_anthropic else ("ollama" if CONFIG.use_ollama else "offline-extractive")
        return f"store:{store} · embed:{emb} · gen:{gen}"

    # -- ingestion ----------------------------------------------------------
    def ingest_path(self, path: str | Path) -> tuple[int, int, list[str]]:
        """Attach a file or folder. Returns (files_added, chunks_added, errors)."""
        files = expand_paths(Path(path))
        new_chunks: list[Chunk] = []
        errors: list[str] = []
        added_files = 0
        for f in files:
            key = str(f.resolve())
            if key in self._ingested:
                continue
            try:
                doc = parse_file(f)
                cks = chunk_document(doc)
            except Exception as exc:  # noqa: BLE001 - surface to the user, keep going
                errors.append(f"{f.name}: {exc}")
                continue
            if not cks:
                continue
            self._ingested.add(key)
            new_chunks.extend(cks)
            added_files += 1

        if new_chunks:
            vectors = self.embedder.embed_chunks(new_chunks)
            self.vs.upsert(new_chunks, vectors)
            self.chunks.extend(new_chunks)
            self.bm25.build(self.chunks)  # rebuild over the full set
            
            if CONFIG.use_graphrag:
                from .ingest.graph import extract_triplets
                for chunk in new_chunks:
                    triplets = extract_triplets(chunk)
                    if triplets:
                        self.graph.add_triplets(triplets)
                        
            self.retriever = HybridRetriever(
                self.vs, self.bm25, self.embedder, self.reranker, graph=self.graph
            )
        return added_files, len(new_chunks), errors

    # -- query --------------------------------------------------------------
    def query(
        self, question: str, filters: dict | None = None, pin_version: str | None = None
    ) -> AnswerResult:
        if not self.chunks:
            return AnswerResult(
                question=question,
                answer="No documents indexed yet. Attach a file or folder first "
                "(e.g. /attach data/corpus).",
                unsupported=True,
                model="n/a",
            )
        return answer_question(self.retriever, question, filters=filters, pin_version=pin_version)
