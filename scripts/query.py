#!/usr/bin/env python3
"""One-off CLI query against the corpus (offline-capable).

Examples:
  python scripts/query.py "what is the max transceiver data rate?"
  python scripts/query.py --doc-type errata "GTP PLL lock failure workaround"
  python scripts/query.py --filter product=XC7A50T --filter stepping=ES1 "known issues"
  python scripts/query.py --pin-version v1.5 "max GTP line rate"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Uses an always-in-memory retriever; no configuration needed.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mmrag.generate.answer import answer_question  # noqa: E402
from mmrag.retriever import build_in_memory_retriever  # noqa: E402


def _print(result) -> None:
    print("\n" + result.answer + "\n")
    for w in result.warnings:
        print(f"  ⚠ {w}")
    print("Sources:")
    if not result.citations:
        print("  (none — answer not grounded)")
    for c in result.citations:
        sup = f"  [superseded by {c.superseded_by}]" if c.superseded_by else ""
        print(f"  • {c.label}{sup}")
        if c.cited_text:
            snippet = c.cited_text.strip().replace("\n", " ")
            print(f"      “{snippet[:160]}”")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+", help="question text")
    ap.add_argument("--doc-type")
    ap.add_argument("--version")
    ap.add_argument("--pin-version")
    ap.add_argument(
        "--filter", action="append", default=[], metavar="KEY=VALUE",
        help="generic metadata filter (repeatable); value may be comma-separated",
    )
    args = ap.parse_args()

    filters: dict = {}
    if args.doc_type:
        filters["doc_type"] = args.doc_type
    if args.version:
        filters["version"] = args.version
    for item in args.filter:
        if "=" in item:
            k, _, v = item.partition("=")
            vals = [p.strip() for p in v.split(",") if p.strip()]
            filters[k.strip()] = vals if len(vals) > 1 else vals[0]

    retriever, _ = build_in_memory_retriever()
    result = answer_question(
        retriever, " ".join(args.question),
        filters=filters or None, pin_version=args.pin_version,
    )
    _print(result)


if __name__ == "__main__":
    main()
