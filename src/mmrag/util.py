"""Small shared helpers."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\w+|[^\w\s]")


def approx_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate.

    Good enough for chunk-size budgeting. For billing-accurate counts against a
    Claude model, use the Anthropic ``messages.count_tokens`` endpoint instead —
    never a third-party tokenizer, which mis-estimates Claude tokens.
    """
    return max(1, round(len(_WORD_RE.findall(text)) * 1.3))


# Part numbers (XC7A35T, EP4CE6, LFE5U-25F) and error/answer-record codes.
PART_RE = re.compile(r"\b[A-Z]{1,4}\d[A-Z0-9\-]{2,}\b")
CODE_RE = re.compile(r"\b(?:AR|EN|XAPP|UG|DS)\d{2,}\b", re.IGNORECASE)


def extract_part_numbers(text: str) -> list[str]:
    found = set(PART_RE.findall(text)) | set(CODE_RE.findall(text.upper()))
    return sorted(found)
