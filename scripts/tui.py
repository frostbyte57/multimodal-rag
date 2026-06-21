#!/usr/bin/env python3
"""Launch the multimodal RAG TUI.

Equivalent to the ``mmrag-tui`` console script. Offline by default (in-memory
store, hash embeddings); set VECTOR_IN_MEMORY=0 + DATABASE_URL + keys for the
full Postgres/Voyage/Claude stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mmrag.tui import main  # noqa: E402

if __name__ == "__main__":
    main()
