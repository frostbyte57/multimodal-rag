"""Voyage AI multimodal embeddings (Anthropic's recommended embedding partner).

``voyage-multimodal-3`` embeds text and images into one shared space, so an
IMAGE chunk and a text query land in the same vector space and are directly
comparable. Text chunks embed their text; IMAGE chunks embed the figure itself
(with the caption as accompanying text). Falls back to caption text if Pillow
isn't installed or the image can't be loaded.
"""

from __future__ import annotations

from ..config import CONFIG
from ..schema import Chunk, ChunkType


class VoyageEmbedder:
    def __init__(self) -> None:
        import voyageai

        self._client = voyageai.Client(api_key=CONFIG.voyage_api_key)
        self._model = CONFIG.embedding_model
        self.dim = CONFIG.embedding_dim
        try:
            from PIL import Image  # noqa: F401

            self._have_pil = True
        except ImportError:  # pragma: no cover - optional dep
            self._have_pil = False

    def _chunk_input(self, chunk: Chunk):
        """Build a multimodal input: a list mixing text and (optionally) a PIL image."""
        if chunk.chunk_type == ChunkType.IMAGE.value and self._have_pil and chunk.image_path:
            from pathlib import Path

            from PIL import Image

            p = Path(chunk.image_path)
            if p.exists():
                content = []
                if chunk.caption:
                    content.append(chunk.caption)
                content.append(Image.open(p).convert("RGB"))
                return content
        return [chunk.embedding_text()]

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(chunks), 64):
            batch = [self._chunk_input(c) for c in chunks[i : i + 64]]
            resp = self._client.multimodal_embed(
                batch, model=self._model, input_type="document"
            )
            out.extend(resp.embeddings)
        return out

    def embed_query(self, text: str) -> list[float]:
        resp = self._client.multimodal_embed(
            [[text]], model=self._model, input_type="query"
        )
        return resp.embeddings[0]
