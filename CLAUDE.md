# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

ReadLoop is a multi-paper research agent harness. It ingests academic PDFs, builds a knowledge graph + long-term memory, and provides cross-paper analysis through an interactive CLI. The core value is linking dozens of papers into a computable knowledge network — not single-paper summarization.

## Commands

```bash
# Install
pip install -e .                            # Dev install
pip install -e ".[leiden]"                   # With Leiden community detection
pip install -e ".[all]"                     # All optional dependencies

# Setup (first-time interactive wizard)
readloop --init                             # Configure LLM keys, paper dirs, output

# Run interactive CLI (primary usage)
readloop                                    # Via entry point
python -m readloop                          # Via module
python run.py                               # Legacy (backward compat)

# Script mode examples
readloop --list                             # List available papers
readloop --single "A-MEM"                   # Analyze one paper by keyword
readloop --build-graph                      # Build knowledge graph
readloop --ask "Which papers discuss X?"    # Semantic Q&A
readloop --help                             # All script options

# Smoke tests (requires generated data in OUTPUT_DIR)
python -m tests.smoke

# Lint (optional, dev dependency)
ruff check readloop/
```

## Architecture

### Data Flow (the critical path)

```
PDF → reader.py (PyMuPDF) → pipeline.py (LLM analysis + memory recall)
  → analysis.md (11-section report)
  → extraction.json (structured entities via LLM)
  → digest.json (compact summary for cross-analysis)
```

Every artifact is incremental: if `analysis.md` / `extraction.json` / `digest.json` already exists, the step is skipped.

### Dual Knowledge Tracks

1. **Knowledge Graph** (`readloop/knowledge/`): Nodes (paper/concept/method/dataset/metric) + Edges (proposes/uses/improves/shared_concept/etc). Stored as `graph.json`. Uses NetworkX via a bridge layer (`nx_bridge.py`) for algorithms — the primary data structure is `KnowledgeGraph` dataclass, not nx.Graph.

2. **Memory System** (`readloop/memory/`): Flat store of `MemoryEntry` items (fact/claim/insight) with embedding-based hybrid search. Stored as `memory_store.json` + `embeddings.npy`.

These two tracks serve different purposes: the graph answers structural questions (communities, god nodes, cross-paper edges), while memory answers semantic questions (Q&A, recall, review generation).

### LLM Client (`readloop/client.py`)

Dual-model failover: DeepSeek V3 primary (capped at 8192 tokens), Claude Sonnet fallback (up to 16K tokens). Both use the OpenAI-compatible API via the `openai` Python SDK. `chat_json()` has a 4-level JSON extraction fallback chain for unreliable LLM output. All API calls wrapped in exponential backoff retry (`readloop/retry.py`) with jitter for 429/timeout/5xx errors. Structured exceptions in `readloop/exceptions.py`.

### Key ID Conventions

- **Node IDs**: `{type}:{slug}` — e.g., `paper:a-mem`, `concept:zettelkasten-memory`
- **Paper IDs**: `make_paper_id()` in `readloop/utils.py` — slugified, 80-char max, shared across all subsystems
- **Memory entry IDs**: SHA-256 first 16 hex chars via `make_entry_id()`
- **Output directories**: `safe_dirname()` from paper name, stored under `OUTPUT_DIR/{safe_name}/`

### Entry Points & Command Architecture

- `readloop` CLI entry point (or `python -m readloop`): argparse script mode when args given, interactive CLI otherwise
- `readloop/cli.py`: Interactive REPL with 23+ slash commands, prompt_toolkit + Rich
- `readloop/_run.py`: argparse script mode logic (also available via `python run.py` for backward compat)
- `readloop/commands/`: Shared command implementations used by both cli.py and _run.py — **single source of truth** for all command logic:
  - `papers.py`: Paper collection, listing, lookup
  - `graph.py`: Knowledge graph build/show/cluster/viz/gaps/gods/questions
  - `memory.py`: Memory build/stats/ask
  - `analysis.py`: Single/batch/cross-paper analysis
  - `export.py`: Wiki and GraphML export
  - `features.py`: Literature review, concept tracking, proposals

### Cross-Paper Analysis Pipeline (4 stages)

In `pipeline.py::generate_cross_analysis()`:
1. **Stage A**: Load per-paper `digest.json` files
2. **Stage B**: LLM generates candidate cross-paper insights
3. **Stage C**: Each insight verified against cited paper evidence
4. **Stage D**: Final report from verified insights only

Falls back to legacy single-prompt mode if Stage B fails.

### Knowledge Feedback Loops

1. **Analysis-time recall** (`memory/recall.py`): Before analyzing a new paper, top-10 semantically similar memories are injected into the LLM prompt.
2. **Q&A feedback** (`memory/search.py`): Each successful `/ask` answer is auto-saved as a low-confidence insight memory.

## Configuration

All config is in `readloop/config.py`, loaded from `.env` via python-dotenv. Key variables:

- `CLAUDE_API_KEY` / `DEEPSEEK_API_KEY`: LLM credentials
- `REFERENCE_DIR_1`, `REFERENCE_DIR_2`: Paper source directories
- `OUTPUT_DIR`: All generated artifacts go here
- `READLOOP_LLM_TRUST_ENV`: Set to `1` only if LLM API needs system proxy
- `READLOOP_MERGE_THRESHOLD`: Cosine similarity for concept canonicalization (default 0.90)

## Storage

Pure JSON + NumPy files, no database. All derived artifacts can be regenerated from `analysis.md` files. Key paths under `OUTPUT_DIR`:

- `{paper}/analysis.md`, `extraction.json`, `digest.json`
- `knowledge_graph/graph.json`, `graph.html`
- `memory/memory_store.json`, `embeddings.npy`, `embedding_ids.json`

## Conventions

- All file I/O uses `encoding="utf-8"` explicitly (Windows compatibility)
- `sys.stdout.reconfigure(encoding="utf-8")` at startup in both `run.py` and `pipeline.py`
- Prompts are string templates in `readloop/prompts.py`, `readloop/knowledge/prompts.py`, `readloop/memory/prompts.py`
- Dataclass models use `from_dict()` / `to_dict()` with unknown-key filtering for forward compatibility
- The `KnowledgeGraph ↔ NetworkX` bridge is one-way for algorithms; results are written back to node `.community` attributes
