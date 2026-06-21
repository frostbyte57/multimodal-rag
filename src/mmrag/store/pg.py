"""Postgres + pgvector dense store with metadata filtering.

Schema (one table, default name ``chunks``):

    id          bigserial primary key
    chunk_id    text
    doc_type    text                 -- first-class filter columns
    version     text
    payload     jsonb                -- the full Chunk (incl. metadata)
    embedding   vector(<dim>)

Cosine distance (``<=>``) ranks results; an ivfflat index accelerates it.
Metadata filters compile to SQL: first-class columns match directly; arbitrary
``metadata`` keys match either a scalar (``payload->'metadata'->>key``) or an
array element (``payload->'metadata'->key ?| array[...]``), so list-valued tags
like steppings work.
"""

from __future__ import annotations

import json

from ..config import CONFIG
from ..schema import Chunk
from .filters import _as_list


class PgVectorStore:
    def __init__(self) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._psycopg = psycopg
        self._register_vector = register_vector
        self.table = CONFIG.pg_table
        self._conn = psycopg.connect(CONFIG.database_url, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)

    def recreate(self, dim: int) -> None:
        self._conn.execute(f"DROP TABLE IF EXISTS {self.table}")
        self._conn.execute(
            f"""
            CREATE TABLE {self.table} (
                id        bigserial PRIMARY KEY,
                chunk_id  text,
                doc_type  text,
                version   text,
                payload   jsonb,
                embedding vector({dim})
            )
            """
        )
        # Approximate-NN index for cosine distance.
        self._conn.execute(
            f"CREATE INDEX ON {self.table} "
            f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        import numpy as np

        with self._conn.cursor() as cur:
            for chunk, vec in zip(chunks, vectors):
                cur.execute(
                    f"INSERT INTO {self.table} "
                    f"(chunk_id, doc_type, version, payload, embedding) "
                    f"VALUES (%s, %s, %s, %s, %s)",
                    (
                        chunk.chunk_id,
                        chunk.doc_type,
                        chunk.version,
                        json.dumps(chunk.to_payload()),
                        np.asarray(vec, dtype=np.float32),
                    ),
                )

    def search(
        self, query_vec: list[float], top_k: int, filters: dict | None = None
    ) -> list[tuple[Chunk, float]]:
        import numpy as np

        where, params = self._compile_filters(filters)
        sql = (
            f"SELECT payload, 1 - (embedding <=> %s) AS score "
            f"FROM {self.table} {where} "
            f"ORDER BY embedding <=> %s LIMIT %s"
        )
        qv = np.asarray(query_vec, dtype=np.float32)
        args = [qv, *params, qv, top_k]
        rows = self._conn.execute(sql, args).fetchall()
        return [(Chunk.from_payload(payload), float(score)) for payload, score in rows]

    def _compile_filters(self, filters: dict | None) -> tuple[str, list]:
        if not filters:
            return "", []
        clauses: list[str] = []
        params: list = []
        for key, wanted in filters.items():
            vals = [str(v) for v in _as_list(wanted) if v not in (None, "")]
            if not vals:
                continue
            if key in {"doc_type", "version"}:
                clauses.append(f"{key} = ANY(%s)")
                params.append(vals)
            else:
                # Match a scalar metadata value OR any element of an array value.
                clauses.append(
                    "((payload->'metadata'->>%s) = ANY(%s) "
                    "OR (payload->'metadata'->%s) ?| %s)"
                )
                params.extend([key, vals, key, vals])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params
