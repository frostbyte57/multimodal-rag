"""Parse a generic per-section metadata annotation into a dict.

Annotation form in the corpus::

    <!-- meta: product=XC7A35T,XC7A50T stepping=ES1 errata_id=EN-101 -->

Comma-separated values become a list (so the retriever can match any element);
single values stay scalar. Merged into the chunk's ``metadata`` dict.
"""

from __future__ import annotations

from typing import Any


def parse_meta_annotation(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for token in raw.split():
        if "=" not in token:
            continue
        key, _, val = token.partition("=")
        key = key.strip()
        parts = [p.strip() for p in val.split(",") if p.strip()]
        if not parts:
            continue
        out[key] = parts if len(parts) > 1 else parts[0]
    return out
