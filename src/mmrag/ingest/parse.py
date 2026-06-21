"""Layout-aware, multimodal parsing into a heading-structured intermediate form.

Two front-ends produce the same ``ParsedDoc``:

* Markdown (``.md``) — document metadata in YAML frontmatter (any keys beyond the
  known ones land in ``metadata``); ``<!-- page: N -->`` comments simulate page
  boundaries; ``<!-- meta: key=val ... -->`` comments attach per-section metadata
  tags; ``![caption](image.png)`` references become IMAGE blocks.
* PDF (``.pdf``) — real documents via PyMuPDF (headings by font size; tables via
  pdfplumber; embedded images extracted as IMAGE blocks). Imported lazily.

Downstream, ``chunk.py`` turns sections into retrievable ``Chunk`` objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..schema import ChunkType, DocMeta

_KNOWN_FM_KEYS = {"doc_id", "title", "doc_type", "version", "version_date", "url"}


@dataclass
class Block:
    text: str
    page: int
    chunk_type: str = ChunkType.TEXT.value
    meta_raw: str | None = None  # generic per-section metadata annotation
    image_path: str | None = None
    caption: str | None = None


@dataclass
class Section:
    number: str
    path: list[str]
    page_start: int
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ParsedDoc:
    meta: DocMeta
    sections: list[Section]


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
_META_RE = re.compile(r"<!--\s*meta:\s*(.*?)\s*-->")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)?\s*(.*)$")
_IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")


def parse_file(path: Path) -> ParsedDoc:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return _parse_markdown(path)
    if suffix == ".pdf":
        return _parse_pdf(path)
    raise ValueError(f"Unsupported document type: {path}")


def _build_meta(fm: dict[str, Any], path: Path) -> DocMeta:
    metadata = {k: v for k, v in fm.items() if k not in _KNOWN_FM_KEYS}
    return DocMeta(
        doc_id=str(fm["doc_id"]),
        title=str(fm["title"]),
        source_path=str(path),
        doc_type=str(fm.get("doc_type", "generic")),
        version=str(fm.get("version", "")),
        version_date=str(fm.get("version_date", "")),
        url=fm.get("url"),
        metadata=metadata,
    )


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def _parse_markdown(path: Path) -> ParsedDoc:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"{path} is missing YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body = raw[m.end() :]
    meta = _build_meta(fm, path)

    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    page = 1
    current: Section | None = None
    table_lines: list[str] = []
    pending_meta: str | None = None
    para_buf: list[str] = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines and current is not None:
            current.blocks.append(Block("\n".join(table_lines), page, ChunkType.TABLE.value))
        table_lines = []

    def flush_para() -> None:
        nonlocal pending_meta, para_buf
        text = "\n".join(para_buf).strip()
        if text and current is not None:
            current.blocks.append(
                Block(text, page, ChunkType.TEXT.value, meta_raw=pending_meta)
            )
            pending_meta = None
        para_buf = []

    for line in body.splitlines():
        page_m = _PAGE_RE.search(line)
        if page_m:
            page = int(page_m.group(1))
            continue
        meta_m = _META_RE.search(line)
        if meta_m:
            pending_meta = meta_m.group(1)
            continue

        heading_m = _HEADING_RE.match(line)
        if heading_m:
            flush_para()
            flush_table()
            level = len(heading_m.group(1))
            number = heading_m.group(2) or ""
            title = heading_m.group(3).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            current = Section(number, [t for _, t in heading_stack], page)
            sections.append(current)
            continue

        img_m = _IMAGE_RE.search(line)
        if img_m and current is not None:
            flush_para()
            flush_table()
            caption = img_m.group(1).strip()
            rel = img_m.group(2).strip()
            img_path = (path.parent / rel).resolve()
            current.blocks.append(
                Block(
                    caption or rel,
                    page,
                    ChunkType.IMAGE.value,
                    meta_raw=pending_meta,
                    image_path=str(img_path),
                    caption=caption,
                )
            )
            pending_meta = None
            continue

        if line.strip().startswith("|"):
            flush_para()
            table_lines.append(line)
            continue
        flush_table()

        if not line.strip():
            flush_para()
        else:
            para_buf.append(line)

    flush_para()
    flush_table()
    return ParsedDoc(meta=meta, sections=sections)


# --------------------------------------------------------------------------- #
# PDF (production path)
# --------------------------------------------------------------------------- #
def _parse_pdf(path: Path) -> ParsedDoc:
    """Parse a real document PDF. Requires a ``<name>.meta.yaml`` sidecar with the
    same fields as the Markdown frontmatter. Headings come from font size,
    tables from pdfplumber, and embedded images are extracted as IMAGE blocks."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - optional dep
        raise RuntimeError(
            "PDF ingestion requires PyMuPDF. Install with: pip install '.[pdf]'"
        ) from exc

    meta_path = path.with_suffix(".meta.yaml")
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Expected sidecar metadata {meta_path} for {path}. "
            "See data/corpus/*.md frontmatter for the field set."
        )
    fm = yaml.safe_load(meta_path.read_text()) or {}
    meta = _build_meta(fm, path)

    doc = fitz.open(path)
    sizes: list[float] = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(round(span["size"], 1))
    body_size = max(set(sizes), key=sizes.count) if sizes else 10.0

    sections: list[Section] = []
    current: Section | None = None
    heading_num_re = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
    img_dir = path.parent / f"{path.stem}_images"
    for page_idx, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line.get("spans", [])).strip()
                if not text:
                    continue
                size = max((s["size"] for s in line.get("spans", [])), default=body_size)
                hm = heading_num_re.match(text)
                if size > body_size * 1.15 and hm:
                    number, title = hm.group(1), hm.group(2)
                    path_crumb = (current.path[:-1] if current else []) + [title]
                    current = Section(number, path_crumb, page_idx)
                    sections.append(current)
                else:
                    if current is None:
                        current = Section("", [meta.title], page_idx)
                        sections.append(current)
                    current.blocks.append(Block(text, page_idx, ChunkType.TEXT.value))
        _extract_pdf_images(doc, page, page_idx, current, img_dir)

    _extract_pdf_tables(path, sections)
    doc.close()
    return ParsedDoc(meta=meta, sections=sections)


def _extract_pdf_images(doc, page, page_idx, current, img_dir) -> None:
    if current is None:
        return
    import fitz  # noqa: F401

    for i, img in enumerate(page.get_images(full=True)):
        try:
            pix = doc.extract_image(img[0])
        except Exception:  # pragma: no cover
            continue
        img_dir.mkdir(parents=True, exist_ok=True)
        out = img_dir / f"p{page_idx}_{i}.{pix['ext']}"
        out.write_bytes(pix["image"])
        current.blocks.append(
            Block(
                f"Figure on page {page_idx}",
                page_idx,
                ChunkType.IMAGE.value,
                image_path=str(out),
                caption=f"Figure on page {page_idx}",
            )
        )


def _extract_pdf_tables(path: Path, sections: list[Section]) -> None:
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - optional dep
        return
    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables() or []:
                rows = ["| " + " | ".join((c or "") for c in row) + " |" for row in table]
                target = None
                for sec in sections:
                    if sec.page_start <= page_idx:
                        target = sec
                if target is not None:
                    target.blocks.append(
                        Block("\n".join(rows), page_idx, ChunkType.TABLE.value)
                    )
