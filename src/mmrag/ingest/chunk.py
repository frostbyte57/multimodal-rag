"""Semantic, heading-aware, multimodal chunking.

Strategy (matches "by section/heading, not fixed token windows"):

* One section's prose becomes one chunk when it fits the token budget.
* Oversized sections split on sentence boundaries with small overlap.
* Tables are emitted as their own chunk and never split mid-row; the section
  heading breadcrumb is prepended so the table is self-describing.
* Images become IMAGE chunks carrying the figure path + caption (the caption is
  used for lexical/BM25 matching and as the offline embedding text).
* Document-level metadata, per-section ``meta`` annotations, and extracted
  codes/identifiers all merge into the chunk's ``metadata`` dict for filtering.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import CONFIG
from ..schema import Chunk, ChunkType, DocMeta
from ..util import approx_tokens, extract_part_numbers
from .metadata import parse_meta_annotation
from .parse import ParsedDoc, Section

_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_document(doc: ParsedDoc) -> list[Chunk]:
    meta = doc.meta
    chunks: list[Chunk] = []
    ordinal = 0

    for section in doc.sections:
        breadcrumb = " > ".join(section.path)
        text_buffer: list[str] = []
        buffer_meta: str | None = None
        buffer_page = section.page_start

        def flush_text() -> None:
            nonlocal ordinal, text_buffer, buffer_meta, buffer_page
            if not text_buffer:
                return
            body = "\n\n".join(text_buffer)
            for piece, page in _split_to_budget(body, buffer_page):
                chunks.append(
                    _make_chunk(meta, section, breadcrumb, piece, page,
                                ChunkType.TEXT.value, buffer_meta, ordinal)
                )
                ordinal += 1
            text_buffer = []
            buffer_meta = None

        for block in section.blocks:
            if block.chunk_type == ChunkType.TABLE.value:
                flush_text()
                table_text = f"Table in section {breadcrumb}:\n{block.text}"
                chunks.append(
                    _make_chunk(meta, section, breadcrumb, table_text, block.page,
                                ChunkType.TABLE.value, block.meta_raw, ordinal)
                )
                ordinal += 1
            elif block.chunk_type == ChunkType.IMAGE.value:
                flush_text()
                caption = block.caption or block.text
                img_text = f"Figure in section {breadcrumb}: {caption}"
                chunks.append(
                    _make_chunk(meta, section, breadcrumb, img_text, block.page,
                                ChunkType.IMAGE.value, block.meta_raw, ordinal,
                                image_path=block.image_path, caption=caption)
                )
                ordinal += 1
            else:
                if not text_buffer:
                    buffer_page = block.page
                if block.meta_raw:
                    buffer_meta = block.meta_raw
                text_buffer.append(block.text)
        flush_text()

    return chunks


def _split_to_budget(text: str, page: int) -> list[tuple[str, int]]:
    budget = CONFIG.max_chunk_tokens
    if approx_tokens(text) <= budget:
        return [(text, page)]

    sentences = _SENT_RE.split(text)
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    overlap = CONFIG.chunk_overlap_tokens
    for sent in sentences:
        st = approx_tokens(sent)
        if cur and cur_tokens + st > budget:
            pieces.append(" ".join(cur))
            carry: list[str] = []
            carry_tokens = 0
            for s in reversed(cur):
                carry_tokens += approx_tokens(s)
                carry.insert(0, s)
                if carry_tokens >= overlap:
                    break
            cur = carry
            cur_tokens = carry_tokens
        cur.append(sent)
        cur_tokens += st
    if cur:
        pieces.append(" ".join(cur))
    return [(p, page) for p in pieces]


def _make_chunk(
    meta: DocMeta,
    section: Section,
    breadcrumb: str,
    text: str,
    page: int,
    chunk_type: str,
    meta_raw: str | None,
    ordinal: int,
    image_path: str | None = None,
    caption: str | None = None,
) -> Chunk:
    metadata: dict[str, Any] = dict(meta.metadata)  # doc-level tags
    metadata.update(parse_meta_annotation(meta_raw))  # section-level tags
    codes = extract_part_numbers(text)
    if codes:
        existing = metadata.get("codes")
        merged = set(codes) | set(existing if isinstance(existing, list) else
                                  ([existing] if existing else []))
        metadata["codes"] = sorted(merged)

    return Chunk(
        chunk_id=Chunk.make_id(meta.doc_id, meta.version, section.number, ordinal),
        doc_id=meta.doc_id,
        text=text,
        title=meta.title,
        doc_type=meta.doc_type,
        version=meta.version,
        version_date=meta.version_date,
        section_number=section.number,
        section_path=section.path,
        page_start=page,
        page_end=page,
        chunk_type=chunk_type,
        token_count=approx_tokens(text),
        url=meta.url,
        metadata=metadata,
        image_path=image_path,
        caption=caption,
    )
