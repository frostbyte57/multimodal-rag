"""Embedder protocol and factory.

The retriever depends only on ``Embedder``; the concrete backend (Voyage
multimodal when a key is present, deterministic hash otherwise) is chosen by
``get_embedder``. ``embed_chunks`` is multimodal-aware — for IMAGE chunks the
Voyage backend embeds the actual image into the shared text/image space, while
the offline backend falls back to the caption text.
"""

from __future__ import annotations

from typing import Protocol

from ..config import CONFIG
from ..schema import Chunk


class Embedder(Protocol):
    dim: int

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def get_embedder() -> Embedder:
    if CONFIG.use_voyage:
        from .voyage import VoyageEmbedder

        return VoyageEmbedder()
    from .hash_fallback import HashEmbedder

    return HashEmbedder(dim=CONFIG.embedding_dim)
