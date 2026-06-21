#!/usr/bin/env python3
"""Evaluate retrieval recall and citation accuracy against eval/questions.yaml.

Runs fully offline by default (in-memory vector store + hash embedder), so it
works in CI with no keys. With ANTHROPIC_API_KEY / VOYAGE_API_KEY set it
exercises the real generation + reranking path, including the negative case.

Metrics:
  * retrieval recall@k  — did an expected (doc, section) appear in the top-k
                          retrieved chunks?
  * citation accuracy   — did the produced answer cite an expected source?
  * abstention accuracy — for negative questions, did the assistant decline?
                          (only meaningful with a generation model configured)

Usage:
  python eval/eval.py [--k 8]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Uses an always-in-memory retriever (no Postgres needed). Generation/reranking
# still activate if keys are configured in .mmrag.json.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from mmrag.config import CONFIG  # noqa: E402
from mmrag.generate.answer import answer_question  # noqa: E402
from mmrag.retriever import build_in_memory_retriever  # noqa: E402


def _section_match(chunk_section: str, expected: str) -> bool:
    if chunk_section == expected:
        return True
    return chunk_section.startswith(expected + ".")


def _matches(chunk, exp: dict) -> bool:
    if chunk.doc_id != exp["doc"]:
        return False
    if "section" in exp and not _section_match(chunk.section_number, str(exp["section"])):
        return False
    if "version" in exp and chunk.version != exp["version"]:
        return False
    return True


def _citation_matches(citation, exp: dict) -> bool:
    if citation.doc_id != exp["doc"]:
        return False
    if "section" in exp and not _section_match(citation.section_number, str(exp["section"])):
        return False
    return True


def run(k: int) -> int:
    questions = yaml.safe_load(CONFIG.eval_path.read_text())
    retriever, chunks = build_in_memory_retriever()
    print(f"Indexed {len(chunks)} chunks. Generation: "
          f"{'Claude ' + CONFIG.generation_model if CONFIG.use_anthropic else 'offline-extractive'}; "
          f"embeddings: {'Voyage' if CONFIG.use_voyage else 'hash-fallback'}.\n")

    recall_hits = recall_total = 0
    cite_hits = cite_total = 0
    abst_hits = abst_total = 0
    failures: list[str] = []

    for q in questions:
        filters = q.get("filters")
        pin = q.get("pin_version")

        if q.get("expect_unsupported"):
            result = answer_question(retriever, q["question"], filters=filters, pin_version=pin)
            if CONFIG.use_anthropic:
                abst_total += 1
                if result.unsupported:
                    abst_hits += 1
                else:
                    failures.append(f"[{q['id']}] did NOT decline an unanswerable question")
            continue

        expected = q["expect"]

        # Retrieval recall@k — pull top-k chunks directly.
        retrieved = retriever.retrieve(q["question"], filters=filters, top_n=k, pin_version=pin)
        got = [r.chunk for r in retrieved]
        recall_total += 1
        if any(_matches(c, e) for c in got for e in expected):
            recall_hits += 1
        else:
            failures.append(
                f"[{q['id']}] recall miss — expected {expected}; "
                f"got {[(c.doc_id, c.section_number, c.version) for c in got[:5]]}"
            )

        # Citation accuracy — does the produced answer cite an expected source?
        result = answer_question(retriever, q["question"], filters=filters, pin_version=pin)
        cite_total += 1
        if any(_citation_matches(c, e) for c in result.citations for e in expected):
            cite_hits += 1
        else:
            failures.append(f"[{q['id']}] citation miss — cited {[c.label for c in result.citations]}")

    print("=" * 64)
    print(f"Retrieval recall@{k:<2}   {recall_hits}/{recall_total}  "
          f"= {recall_hits / max(recall_total, 1):.1%}")
    print(f"Citation accuracy     {cite_hits}/{cite_total}  "
          f"= {cite_hits / max(cite_total, 1):.1%}")
    if abst_total:
        print(f"Abstention accuracy   {abst_hits}/{abst_total}  "
              f"= {abst_hits / max(abst_total, 1):.1%}")
    else:
        print("Abstention accuracy   n/a (needs ANTHROPIC_API_KEY)")
    print("=" * 64)

    if failures:
        print("\nDetails:")
        for f in failures:
            print("  -", f)

    # Non-zero exit if retrieval recall drops below a floor (CI gate).
    return 0 if recall_hits / max(recall_total, 1) >= 0.8 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=CONFIG.rerank_top_n)
    args = ap.parse_args()
    raise SystemExit(run(args.k))
