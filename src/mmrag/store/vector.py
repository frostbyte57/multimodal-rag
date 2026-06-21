"""Vector store: factory.

``get_vector_store()`` returns the pgvector-backed store in production
(``DATABASE_URL``).

    recreate(dim)                -> reset/create storage for ``dim``-d vectors
    upsert(chunks, vectors)      -> add chunks with their embeddings
    search(qvec, top_k, filters) -> [(Chunk, score)] by cosine similarity
"""

from __future__ import annotations

from .pg import PgVectorStore

def get_vector_store():
    return PgVectorStore()
