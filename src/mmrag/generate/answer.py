"""Grounded answer generation: retrieve → generate → verify.

Production path uses Claude Opus 4.8 with the native Citations API: each
retrieved chunk is a ``document`` block with citations enabled, so the model's
answer comes back split into text blocks that each carry exact ``cited_text`` +
page references pointing at specific source chunks. That makes "every claim must
cite a source" verifiable rather than aspirational.

Offline (no ANTHROPIC_API_KEY) the generator degrades to an extractive answer
built from the top retrieved chunks, so the API and eval stay runnable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..config import CONFIG
from ..schema import ChunkType
from ..store.hybrid import HybridRetriever, RetrievalResult

SYSTEM_PROMPT = """You are a grounded document assistant.

Rules — these are non-negotiable:
- Answer ONLY from the provided documents and figures. Do not use outside knowledge.
- Cite every factual claim. Each sentence stating a fact must be grounded in a
  document you were given. You may also describe what a provided figure shows.
- If the sources do not contain the answer, say exactly: "I don't have a sourced
  answer for that in the indexed documents." Do not guess.
- Prefer the newest document revision when sources conflict, unless the user
  asked about a specific version.
- Be precise and concise: the answer and its source, not filler.
"""


@dataclass
class Citation:
    chunk_id: str
    doc_id: str
    label: str
    cited_text: str
    page: int
    section_number: str
    url: str | None = None
    superseded_by: str | None = None


@dataclass
class AnswerResult:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    unsupported: bool = False
    warnings: list[str] = field(default_factory=list)
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [asdict(c) for c in self.citations],
            "retrieved": self.retrieved,
            "unsupported": self.unsupported,
            "warnings": self.warnings,
            "model": self.model,
        }


def _retrieved_summary(results: list[RetrievalResult]) -> list[dict]:
    return [
        {
            "chunk_id": r.chunk.chunk_id,
            "doc_id": r.chunk.doc_id,
            "label": r.chunk.citation_label(),
            "section": r.chunk.section_number,
            "page": r.chunk.page_start,
            "score": round(r.score, 4),
            "sources": r.sources,
            "url": r.chunk.url,
        }
        for r in results
    ]


def answer_question(
    retriever: HybridRetriever,
    question: str,
    filters: dict | None = None,
    pin_version: str | None = None,
) -> AnswerResult:
    from ..agent import expand_query
    expanded_queries = expand_query(question)
    
    results = retriever.retrieve(
        question, 
        filters=filters, 
        pin_version=pin_version,
        expanded_queries=expanded_queries
    )
    retrieved = _retrieved_summary(results)

    if not results:
        return AnswerResult(
            question=question,
            answer="I don't have a sourced answer for that in the indexed documents.",
            unsupported=True,
            model=CONFIG.generation_model if CONFIG.use_anthropic else "offline",
        )

    if CONFIG.use_anthropic:
        return _generate_with_claude(question, results, retrieved)
    return _extractive_fallback(question, results, retrieved)


def _generate_with_claude(
    question: str, results: list[RetrievalResult], retrieved: list[dict]
) -> AnswerResult:
    import anthropic

    client = anthropic.Anthropic(api_key=CONFIG.anthropic_api_key)

    # Exactly one document block per retrieved chunk (citations enabled), so the
    # citation document_index maps back to results[index]. IMAGE chunks also get
    # an image block before their caption document, giving the model the actual
    # figure to ground on; image blocks don't count toward document_index.
    content: list[dict] = []
    for r in results:
        if r.chunk.chunk_type == ChunkType.IMAGE.value:
            loaded = r.chunk.load_image_b64()
            if loaded:
                media_type, b64 = loaded
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    }
                )
        content.append(
            {
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": r.chunk.metadata.get("parent_text", r.chunk.text),
                },
                "title": r.chunk.citation_label(),
                "citations": {"enabled": True},
            }
        )
    content.append(
        {
            "type": "text",
            "text": (
                f"Question: {question}\n\n"
                "Answer using only the documents above, citing each claim."
            ),
        }
    )

    resp = client.messages.create(
        model=CONFIG.generation_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    answer_parts: list[str] = []
    citations: list[Citation] = []
    uncited_claim = False
    for block in resp.content:
        if block.type != "text":
            continue
        text = block.text
        answer_parts.append(text)
        block_citations = getattr(block, "citations", None) or []
        if block_citations:
            for cit in block_citations:
                idx = getattr(cit, "document_index", None)
                if idx is None or idx >= len(results):
                    continue
                chunk = results[idx].chunk
                page = getattr(cit, "start_page_number", None) or chunk.page_start
                citations.append(
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        label=chunk.citation_label(),
                        cited_text=getattr(cit, "cited_text", ""),
                        page=int(page),
                        section_number=chunk.section_number,
                        url=chunk.url,
                        superseded_by=chunk.superseded_by,
                    )
                )
        elif _looks_like_claim(text):
            uncited_claim = True

    answer = "".join(answer_parts).strip()
    unsupported = (
        "i don't have a sourced answer" in answer.lower() or not citations
    )

    warnings: list[str] = []
    if uncited_claim and not unsupported:
        warnings.append(
            "Some answer text was not backed by a citation — treat with caution."
        )

    return AnswerResult(
        question=question,
        answer=answer,
        citations=_dedupe_citations(citations),
        retrieved=retrieved,
        unsupported=unsupported,
        warnings=warnings,
        model=CONFIG.generation_model,
    )


def _extractive_fallback(
    question: str, results: list[RetrievalResult], retrieved: list[dict]
) -> AnswerResult:
    """No generator configured: surface the top sources verbatim, fully cited."""
    top = results[:3]
    lines = [
        "(Offline mode — no generation model configured. Showing the most "
        "relevant sourced passages.)\n",
    ]
    citations: list[Citation] = []
    for r in top:
        c = r.chunk
        snippet = c.text.strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        lines.append(f"• [{c.citation_label()}] {snippet}")
        citations.append(
            Citation(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                label=c.citation_label(),
                cited_text=snippet,
                page=c.page_start,
                section_number=c.section_number,
                url=c.url,
                superseded_by=c.superseded_by,
            )
        )
    return AnswerResult(
        question=question,
        answer="\n".join(lines),
        citations=citations,
        retrieved=retrieved,
        unsupported=False,
        model="offline-extractive",
    )


def _looks_like_claim(text: str) -> bool:
    stripped = text.strip()
    # Ignore pure connective/whitespace fragments between cited spans.
    return len(stripped) > 30


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for c in citations:
        key = (c.chunk_id, c.cited_text[:50])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
