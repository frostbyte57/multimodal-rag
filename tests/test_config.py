import json

from mmrag.config import Config


def test_defaults_are_offline():
    c = Config()
    assert c.vector_in_memory is True
    assert c.anthropic_api_key is None
    assert c.use_anthropic is False
    assert c.use_voyage is False


def test_update_coerces_types():
    c = Config()
    c.update(embedding_dim="512", max_chunk_tokens="800", vector_in_memory="false")
    assert c.embedding_dim == 512
    assert c.max_chunk_tokens == 800
    assert c.vector_in_memory is False


def test_update_blank_api_key_becomes_none():
    c = Config()
    c.update(anthropic_api_key="sk-test")
    assert c.anthropic_api_key == "sk-test"
    c.update(anthropic_api_key="")
    assert c.anthropic_api_key is None


def test_update_ignores_unknown_and_runtime_keys():
    c = Config()
    c.update(corpus_dir="/evil", nonsense=1)  # not persisted/editable
    assert "corpus_dir" not in c.to_dict()


def test_save_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / ".mmrag.json"
    monkeypatch.setattr("mmrag.config.CONFIG_PATH", path)
    c = Config()
    c.update(generation_model="claude-haiku-4-5", voyage_api_key="vk", embedding_dim="768")
    saved = c.save()
    assert saved == path
    data = json.loads(path.read_text())
    assert data["generation_model"] == "claude-haiku-4-5"
    assert data["embedding_dim"] == 768
    # secrets are persisted (locally) so the TUI restores them next launch
    assert data["voyage_api_key"] == "vk"

    loaded = Config.load()
    assert loaded.generation_model == "claude-haiku-4-5"
    assert loaded.embedding_dim == 768
    assert loaded.use_voyage is True
