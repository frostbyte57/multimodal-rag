from pathlib import Path

from mmrag.ingest.chunk import chunk_document
from mmrag.ingest.parse import parse_file
from mmrag.schema import ChunkType, DocType

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


def _chunks_for(name: str):
    return chunk_document(parse_file(CORPUS / name))


def test_frontmatter_and_sections():
    chunks = _chunks_for("ds181_artix7_datasheet_v1.8.md")
    assert chunks
    c = chunks[0]
    assert c.doc_id == "DS181"
    assert c.doc_type == DocType.DATASHEET  # str compares equal to the enum value
    assert c.version == "v1.8"
    assert any(ch.section_number == "2.1" for ch in chunks)


def test_section_breadcrumb_path():
    chunks = _chunks_for("ds181_artix7_datasheet_v1.8.md")
    sub = next(ch for ch in chunks if ch.section_number == "2.1")
    assert "Transceiver Specifications" in " ".join(sub.section_path)


def test_tables_are_their_own_chunk():
    chunks = _chunks_for("ds181_artix7_datasheet_v1.8.md")
    tables = [c for c in chunks if c.chunk_type == ChunkType.TABLE.value]
    assert tables
    assert any("F_LINE_MAX" in t.text for t in tables)


def test_unknown_frontmatter_goes_to_metadata():
    # part_family is not a known top-level field anymore — it lands in metadata.
    chunks = _chunks_for("ds181_artix7_datasheet_v1.8.md")
    assert any(c.metadata.get("part_family") == "Artix-7" for c in chunks)


def test_meta_annotation_extracted():
    chunks = _chunks_for("artix7_errata.md")
    en101 = next(c for c in chunks if c.metadata.get("errata_id") == "EN-101")
    assert "ES1" in _as_list(en101.metadata.get("stepping"))
    assert "XC7A35T" in _as_list(en101.metadata.get("product"))


def test_codes_detected_into_metadata():
    chunks = _chunks_for("ds181_artix7_datasheet_v1.8.md")
    assert any("XC7A35T" in _as_list(c.metadata.get("codes")) for c in chunks)


def test_pages_tracked():
    chunks = _chunks_for("ug470_artix7_config_userguide.md")
    jtag = next(c for c in chunks if c.section_number == "4")
    assert jtag.page_start == 4


def test_image_chunk_created():
    chunks = _chunks_for("streamflow_architecture_guide.md")
    images = [c for c in chunks if c.chunk_type == ChunkType.IMAGE.value]
    assert images, "expected an IMAGE chunk from the figure reference"
    img = images[0]
    assert img.image_path and img.image_path.endswith("pipeline_arch.png")
    assert img.caption
    # The image file should actually exist and be loadable.
    assert img.load_image_b64() is not None


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]
