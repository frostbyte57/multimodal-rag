"""Central configuration — file-backed, no environment variables.

All settings live in a JSON file (``.mmrag.json`` at the project root) and are
edited from the TUI's settings screen. ``CONFIG`` is a singleton loaded at
import; the TUI mutates it and calls ``CONFIG.save()``. Other entry points
(scripts, API, eval) read the same file, so the TUI is the single source of
truth for configuration.

Defaults are fully offline (in-memory vector store, no API keys), so the system
runs with zero setup; switch to Postgres/Voyage/Claude from the settings screen.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / ".mmrag.json"

# Fields that are persisted to / loaded from the config file and editable in the
# TUI. Runtime-only paths (corpus_dir, …) are exposed as properties below.
PERSISTED = {
    "generation_model",
    "embedding_model",
    "rerank_model",
    "embedding_dim",
    "anthropic_api_key",
    "voyage_api_key",
    "database_url",
    "pg_table",
    "vector_in_memory",
    "max_chunk_tokens",
    "chunk_overlap_tokens",
    "dense_top_k",
    "bm25_top_k",
    "rrf_k",
    "rerank_top_n",
    "prefer_latest_revision",
    "use_hyde",
    "use_graphrag",
}


@dataclass
class Config:
    # --- Models ---
    generation_model: str = "claude-opus-4-8"
    embedding_model: str = "voyage-multimodal-3"
    rerank_model: str = "rerank-2.5"
    embedding_dim: int = 1024

    # --- Keys (empty = offline; set from the TUI settings screen) ---
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None

    # --- Vector store: Postgres + pgvector (or in-memory) ---
    database_url: str = "postgresql://mmrag:mmrag@localhost:5432/mmrag"
    pg_table: str = "chunks"
    vector_in_memory: bool = True  # default offline; switch to pgvector in the TUI

    # --- Chunking ---
    max_chunk_tokens: int = 500
    chunk_overlap_tokens: int = 60

    # --- Retrieval ---
    dense_top_k: int = 40
    bm25_top_k: int = 40
    rrf_k: int = 60
    rerank_top_n: int = 8
    prefer_latest_revision: bool = True
    use_hyde: bool = False
    use_graphrag: bool = False

    # --- Runtime-only paths (not persisted) ---
    @property
    def corpus_dir(self) -> Path:
        return ROOT / "data" / "corpus"

    @property
    def eval_path(self) -> Path:
        return ROOT / "eval" / "questions.yaml"

    @property
    def bm25_index_path(self) -> Path:
        return ROOT / "data" / "bm25.pkl"
        
    @property
    def graph_index_path(self) -> Path:
        return ROOT / "data" / "graph.json"

    @property
    def use_voyage(self) -> bool:
        return bool(self.voyage_api_key)

    @property
    def use_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    # --- Persistence ---
    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
            cfg.update(**data)
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k in PERSISTED}

    def update(self, **values: Any) -> None:
        valid = {f.name for f in fields(self)}
        for key, val in values.items():
            if key not in PERSISTED or key not in valid:
                continue
            current = getattr(self, key)
            # Coerce to the existing field's type where unambiguous.
            if isinstance(current, bool):
                val = val if isinstance(val, bool) else str(val).strip().lower() in {"1", "true", "yes", "on"}
            elif isinstance(current, int) and val is not None:
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    continue
            elif val == "":
                val = None if key.endswith("_api_key") else current
            setattr(self, key, val)

    def save(self) -> Path:
        CONFIG_PATH.write_text(json.dumps(self.to_dict(), indent=2))
        return CONFIG_PATH


CONFIG = Config.load()
