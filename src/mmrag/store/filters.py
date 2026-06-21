"""Generic metadata filter predicate, shared by every vector backend.

A filter is a flat ``dict``. Each key is matched against either a first-class
chunk attribute (``doc_type``, ``version``) or, failing that, the chunk's
``metadata`` dict. Values may be a scalar or a list; a list means "match any".
List-valued chunk fields (e.g. ``metadata["stepping"] = ["ES1", "ES2"]``) match
if they intersect the requested values.
"""

from __future__ import annotations

from ..schema import Chunk

_FIRST_CLASS = {"doc_type", "version"}


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def passes_filter(chunk: Chunk, filters: dict | None) -> bool:
    if not filters:
        return True
    for key, wanted in filters.items():
        if wanted in (None, "", [], {}):
            continue
        wanted_set = set(map(str, _as_list(wanted)))
        if key in _FIRST_CLASS:
            actual = {str(getattr(chunk, key))}
        else:
            actual = set(map(str, _as_list(chunk.metadata.get(key))))
        if not (wanted_set & actual):
            return False
    return True
