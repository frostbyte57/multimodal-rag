"""Core data model for documents and chunks.

Domain-agnostic: a chunk carries a generic ``metadata`` dict for arbitrary
domain tags (e.g. ``{"product": "Artix-7", "stepping": ["ES1"]}``) that the
retriever can filter on, plus first-class fields that the citation and
revision-resolution logic always needs (``doc_id``, ``version``,
``section_number``, ``page_start``).

Multimodal: a chunk may be TEXT, TABLE, or IMAGE. IMAGE chunks carry an
``image_path`` (and an optional ``caption`` used for lexical/BM25 matching and
as the offline embedding text). The generator passes image chunks to a
vision-capable model as image blocks.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DocType(str, Enum):
    """Common document types. ``doc_type`` is stored as a plain string, so any
    value is allowed; these constants exist for convenience and comparison."""

    DATASHEET = "datasheet"
    APP_NOTE = "app_note"
    ERRATA = "errata"
    USER_GUIDE = "user_guide"
    REPORT = "report"
    ARTICLE = "article"
    MANUAL = "manual"
    GENERIC = "generic"


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


@dataclass
class DocMeta:
    """Document-level metadata. One per source file."""

    doc_id: str
    title: str
    source_path: str
    doc_type: str = DocType.GENERIC.value
    version: str = ""
    version_date: str = ""  # ISO 8601; used for revision-conflict resolution
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    """A retrievable unit. Carries everything needed to cite it back."""

    chunk_id: str
    doc_id: str
    text: str
    title: str
    doc_type: str
    version: str
    version_date: str
    section_number: str
    section_path: list[str]
    page_start: int
    page_end: int
    chunk_type: str = ChunkType.TEXT.value
    token_count: int = 0
    url: str | None = None
    # Arbitrary domain tags for metadata filtering (values are str or list[str]).
    metadata: dict[str, Any] = field(default_factory=dict)
    # Multimodal payload (IMAGE chunks only).
    image_path: str | None = None
    caption: str | None = None
    # Set when a newer revision of the same doc supersedes this chunk's doc.
    superseded_by: str | None = None

    @staticmethod
    def make_id(doc_id: str, version: str, section_number: str, ordinal: int) -> str:
        # Version is part of the key: the same doc_id/section across two
        # revisions must produce distinct chunk ids, or RRF fusion collapses them.
        raw = f"{doc_id}|{version}|{section_number}|{ordinal}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def citation_label(self) -> str:
        """Short human-readable handle, e.g. 'DS181 v1.8 §3.2 p.12'."""
        ver = f" {self.version}" if self.version else ""
        sec = f" §{self.section_number}" if self.section_number else ""
        return f"{self.doc_id}{ver}{sec} p.{self.page_start}".strip()

    def embedding_text(self) -> str:
        """Text used for the dense embedding (caption stands in for an image)."""
        if self.chunk_type == ChunkType.IMAGE.value:
            return self.caption or self.text or "image"
        return self.text

    def load_image_b64(self) -> tuple[str, str] | None:
        """Return (media_type, base64) for an IMAGE chunk, or None."""
        if self.chunk_type != ChunkType.IMAGE.value or not self.image_path:
            return None
        p = Path(self.image_path)
        if not p.exists():
            return None
        media = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(p.suffix.lower(), "image/png")
        return media, base64.standard_b64encode(p.read_bytes()).decode()

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Chunk":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in payload.items() if k in valid})
