from mmrag.generate.answer import answer_question
from mmrag.retriever import build_in_memory_retriever
from mmrag.schema import ChunkType


def _retriever():
    retriever, _ = build_in_memory_retriever()
    return retriever


def test_revision_conflict_prefers_latest():
    r = _retriever()
    results = r.retrieve("maximum GTP transceiver line rate on Artix-7", top_n=8)
    ds181 = [x for x in results if x.chunk.doc_id == "DS181" and x.chunk.section_number == "2.1"]
    assert ds181, "expected the GTP spec section to be retrieved"
    versions = {x.chunk.version for x in ds181}
    assert versions == {"v1.8"}


def test_pin_version_returns_older_revision():
    r = _retriever()
    results = r.retrieve("maximum GTP line rate on Artix-7", pin_version="v1.5", top_n=8)
    versions = {x.chunk.version for x in results if x.chunk.doc_id == "DS181"}
    assert versions == {"v1.5"}


def test_metadata_filter_by_arbitrary_key():
    # part_family is a generic metadata key now, not a first-class field.
    r = _retriever()
    results = r.retrieve(
        "maximum transceiver data rate", filters={"part_family": "Cyclone IV"}, top_n=8
    )
    assert results
    assert all(x.chunk.metadata.get("part_family") == "Cyclone IV" for x in results)


def test_metadata_filter_by_stepping():
    r = _retriever()
    results = r.retrieve("known issues", filters={"stepping": "ES1"}, top_n=8)
    assert results
    # Every result must carry the ES1 stepping tag (scalar or list).
    for x in results:
        stepping = x.chunk.metadata.get("stepping")
        vals = stepping if isinstance(stepping, list) else [stepping]
        assert "ES1" in vals


def test_bm25_finds_error_code():
    r = _retriever()
    results = r.retrieve("EN-118 SPI configuration", top_n=8)
    assert any(x.chunk.metadata.get("errata_id") == "EN-118" for x in results)


def test_doc_type_filter():
    r = _retriever()
    results = r.retrieve("known issues and workarounds", filters={"doc_type": "errata"}, top_n=8)
    assert results
    assert all(x.chunk.doc_type == "errata" for x in results)


def test_answer_is_grounded_with_citations():
    r = _retriever()
    res = answer_question(r, "What is the VCCAUX voltage for Artix-7?")
    assert res.citations
    assert any(c.doc_id == "DS181" for c in res.citations)


def test_image_chunk_is_retrievable():
    r = _retriever()
    results = r.retrieve("StreamFlow high-level architecture diagram of the planes", top_n=8)
    assert any(x.chunk.chunk_type == ChunkType.IMAGE.value for x in results)


def test_general_nonfpga_doc_answered():
    r = _retriever()
    res = answer_question(r, "How does StreamFlow guarantee exactly-once processing?")
    assert any(c.doc_id == "SFG100" for c in res.citations)
