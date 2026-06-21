#!/usr/bin/env python3
"""Ingest the corpus into the persistent stores (Postgres/pgvector + on-disk BM25).

Run this once (and after corpus changes) before starting the API in persistent
mode. For the zero-setup offline demo, you can skip this and run the API with
VECTOR_IN_MEMORY=1, which ingests at startup.

Usage:
  python scripts/ingest.py [--corpus data/corpus]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mmrag.config import CONFIG  # noqa: E402
from mmrag.ingest.pipeline import ingest  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CONFIG.corpus_dir)
    args = ap.parse_args()
    chunks = ingest(args.corpus)
    print(f"\nDone. {len(chunks)} chunks indexed.")
