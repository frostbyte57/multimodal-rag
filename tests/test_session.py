from pathlib import Path

from mmrag.session import RagSession, expand_paths

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


def test_expand_file_and_dir():
    assert expand_paths(CORPUS / "streamflow_architecture_guide.md")
    files = expand_paths(CORPUS)
    assert len(files) >= 5  # several corpus docs


def test_empty_session_declines():
    s = RagSession()
    assert s.chunk_count == 0
    res = s.query("anything")
    assert res.unsupported


def test_incremental_ingest_and_query():
    s = RagSession()
    files, chunks, errors = s.ingest_path(CORPUS / "ds181_artix7_datasheet_v1.8.md")
    assert files == 1 and chunks > 0 and not errors
    res = s.query("What is the VCCAUX voltage for Artix-7?")
    assert any(c.doc_id == "DS181" for c in res.citations)


def test_reattach_is_deduped():
    s = RagSession()
    f1, c1, _ = s.ingest_path(CORPUS)
    before = s.chunk_count
    f2, c2, _ = s.ingest_path(CORPUS)  # same folder again
    assert f2 == 0 and c2 == 0
    assert s.chunk_count == before


def test_attach_folder_indexes_images():
    s = RagSession()
    s.ingest_path(CORPUS)
    assert s.image_count >= 1  # the StreamFlow figure
