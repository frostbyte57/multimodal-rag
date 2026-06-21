# Multimodal RAG

A domain-agnostic, multimodal retrieval-augmented generation (RAG) system that answers questions grounded in text and figures with verifiable citations.

```
docs/PDFs ──▶ Parse (text, tables, images) ──▶ Semantic Chunking ──▶ Hybrid Retrieval (pgvector + BM25) ──▶ Voyage Rerank ──▶ Claude (Vision + Citations) ──▶ TUI
```

## Key Features

- **Multimodal Embedding & Retrieval**: Text and images are embedded in a shared space using Voyage. Images are passed directly to Claude for grounding.
- **Verifiable Citations**: Returns exact source citations (page and section) natively validated against retrieved chunks.
- **Hybrid Retrieval**: Combines dense vector search (pgvector) with BM25 keyword search, fused via Reciprocal Rank Fusion (RRF).
- **Revision-Aware**: Automatically resolves section updates using document dates, with manual version pinning.
- **Runs Offline**: Fallback in-memory store and offline embedder for zero-setup execution (ideal for CI).

---

## Directory Structure

- `src/mmrag/`: Core implementation (schema, storage, embedding, generation, TUI).
- `data/corpus/`: Sample documents.
- `eval/`: Retrieval evaluation script and questions.
- `scripts/`: Ingest and query CLI scripts.
- `tests/`: Offline test suites.

---

## Quickstart

### 1. Offline Mode (No Setup)

```bash
# Set up environment
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,tui]"

# Launch interactive Terminal UI
mmrag-tui

# Or query via CLI
python scripts/query.py "How does StreamFlow guarantee exactly-once processing?"
```

### 2. Production Mode (Claude + Voyage + Postgres)

```bash
# Install production dependencies and start database
pip install -e ".[cloud,pdf]"
docker compose up -d

# Open TUI configuration (Press F2), configure keys/database, and ingest
mmrag-tui
python scripts/ingest.py
```

---

## Terminal UI (TUI)

Launch the interactive dashboard with:
```bash
mmrag-tui
```

### Commands
- `<question>`: Ask a question.
- `/attach <path>`: Ingest a file or directory.
- `/reload`: Re-scan `data/corpus/`.
- `/filter <key>=<value>`: Filter by metadata (e.g. `/filter doc_type=errata`).
- `/pin <version>`: Pin a specific revision (e.g. `/pin v1.5`).
- `/docs`: List indexed documents.
- `/config`: Open settings (or press `F2`).
- `/help` | `/quit`

---

## Evaluation

Run the evaluation suite (Recall@k, citation accuracy, CI gates):
```bash
python eval/eval.py
```
