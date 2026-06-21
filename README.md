# Multimodal RAG

A domain-agnostic, **multimodal** retrieval-augmented assistant. It answers
questions grounded in a corpus of documents **and figures**, with **verifiable
citations** back to the exact source section and page. An answer with no
traceable source is treated as a bug.

```
docs / figures / PDFs ─▶ parse (layout-aware, images) ─▶ semantic chunk
   (text · tables · IMAGE)                                  (by heading; tables/figures kept whole)
                                              │
                              ┌───────────────┴───────────────┐
                   Postgres + pgvector (dense)          BM25 (keyword)
                   multimodal embeddings                exact ids/codes
                              └───────────────┬───────────────┘
   query ─▶ metadata filter ─▶ RRF fusion ─▶ revision resolver ─▶ Voyage rerank
                                              │
                Claude Opus 4.8  (retrieve → generate → verify; native Citations + vision)
                                              │
                    Textual TUI ─▶ answer + citations (attach files/folders)
```

## What makes it multimodal & general

- **Text + images in one space.** Figures become first-class IMAGE chunks
  (caption + image). With Voyage `voyage-multimodal-3`, text and images embed
  into a shared space, so a text query can retrieve a relevant diagram; the
  generator passes retrieved figures to Claude as image blocks for visual
  grounding.
- **Domain-agnostic.** No hard-coded domain. Each chunk carries a generic
  `metadata` dict; you filter on arbitrary keys (`product`, `stepping`,
  `component`, `doc_type`, …). The sample corpus mixes a data-platform
  architecture guide (with a figure) and a set of technical hardware docs to
  show the same pipeline handles both.

## Why this design

- **Citations are structural, not best-effort.** Retrieved chunks are passed to
  Claude as `document` blocks with the native Citations API enabled, so the
  answer comes back split into spans that each carry exact `cited_text` + page.
  The verify step flags any answer text not backed by a citation.
- **Hybrid retrieval.** Dense embeddings for semantics + BM25 for exact tokens
  (codes, identifiers), fused with Reciprocal Rank Fusion, then cross-encoder
  reranked.
- **Revision-aware.** When two document revisions cover the same section, the
  newest `version_date` wins — unless the user pins a version.
- **Runs offline.** With no keys it falls back to a deterministic hash embedder,
  an in-memory vector store, and an extractive answerer, so ingestion,
  retrieval, and the retrieval eval run with zero external dependencies (CI).

## Layout

```
src/mmrag/
  schema.py            Chunk / DocMeta model (generic metadata + IMAGE chunks)
  config.py            Env-driven config; key presence toggles cloud vs offline
  ingest/              parse (md + pdf, images) → chunk (heading-aware) → meta tags
  embed/               Voyage multimodal embedder + offline hash fallback
  store/               pg.py (pgvector), vector.py (in-memory + factory),
                       bm25.py, filters.py (generic), hybrid.py (RRF + revisions)
  rerank/              Voyage rerank-2.5
  generate/answer.py   Claude + Citations + vision + verify
  session.py           Interactive session with incremental ingestion
  tui.py               Textual terminal UI (attach files/folders, ask, configure)
data/corpus/           Sample docs (technical docs + a figure-bearing guide)
eval/                  questions.yaml (28 Q's incl. multimodal + filters) + eval.py
scripts/               ingest.py, query.py
tests/                 ingestion + retrieval tests (offline)
```

## TUI (terminal interface)

An interactive terminal UI where you **attach files/folders** and ask questions.

```bash
pip install -e ".[tui]"
mmrag-tui                       # or: python scripts/tui.py
```

It loads `data/corpus/` on startup; then in the prompt:

```
<your question>            ask anything — answer + clickable-style citations
/attach <path>             ingest a file or folder (recurses), e.g. /attach ~/papers
/reload                    re-scan data/corpus/ after dropping new files into it
/filter doc_type=errata    filter retrieval by metadata (repeatable); /filter clears
/pin v1.5                  pin a document revision; /pin clears
/docs                      list indexed documents
/config                    settings: API keys, models, vector store (also F2)
/help   /quit
```

Two ways to add documents: **attach** any path from inside the TUI, or **drop
files** into `data/corpus/` and run `/reload`.

### Configuration — all in the TUI, no environment variables

Press **F2** (or `/config`) to open settings: Anthropic / Voyage API keys,
models, and the vector store (`memory` or `postgres` + its URL). Saving writes
`.mmrag.json` (git-ignored) and re-indexes in place. The same file is read by
the scripts and API, so the TUI is the single source of truth — there are **no
environment variables**. Defaults are fully offline, so a fresh checkout runs
with zero setup.

## Quickstart (offline — no keys, no setup)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,tui]"

mmrag-tui                                                          # interactive TUI
python scripts/query.py "How does StreamFlow guarantee exactly-once processing?"
python scripts/query.py --filter stepping=ES1 "known issues"
python eval/eval.py
```

## Production setup (Claude + Voyage + Postgres/pgvector)

```bash
pip install -e ".[cloud,pdf]"
docker compose up -d          # Postgres + pgvector on :5432 (container: multimodal_rag)

mmrag-tui                     # press F2 → set API keys + store=postgres, save
# or run scripts/ingest.py once .mmrag.json is configured via the TUI
python scripts/ingest.py      # parse → embed → index into pgvector
```

Once configured (keys present, store = postgres), generation uses **Claude Opus
4.8** (citations + vision), embeddings use **Voyage `voyage-multimodal-3`**, the
**rerank-2.5** reranker selects the final top-k, and dense vectors live in
**Postgres/pgvector**.

### Ingesting real PDFs

Drop `*.pdf` into `data/corpus/` with a `<name>.meta.yaml` sidecar (same fields
as the Markdown frontmatter). PDF parsing (PyMuPDF for layout/headings,
pdfplumber for tables, embedded-image extraction) needs the `pdf` extra.

## Chunking & metadata schema

Chunking is **semantic, by heading** — never fixed token windows. Tables and
figures are emitted as their own chunks (never split). Each chunk carries:
`doc_id, title, doc_type, version, version_date, section_number, section_path[],
page_start/end, chunk_type{text|table|image}, metadata{}, image_path, caption`.
`version`/`version_date` drive revision resolution; `section_number` +
`page_start` drive citations; `metadata` drives arbitrary filtering.

In Markdown sources: YAML frontmatter = doc metadata (unknown keys → `metadata`);
`<!-- page: N -->` = page boundaries; `<!-- meta: key=val ... -->` = per-section
tags; `![caption](path.png)` = a figure.

## Eval

`eval/questions.yaml` holds 28 questions with expected sources — including a
revision-conflict case, a version pin, generic metadata filtering, a multimodal
figure question, a cross-document negative case, and questions over a non-FPGA
document. `eval/eval.py` reports retrieval recall@k, citation accuracy, and
(with a model configured) abstention accuracy; it exits non-zero if recall drops
below 80% (CI gate). Current offline baseline: **recall@8 ≈ 96%**.
