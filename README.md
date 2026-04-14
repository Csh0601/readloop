# ReadLoop

> Turn "read once, forget forever" into reusable research assets.

ReadLoop is an **agent harness for multi-paper research**: it ingests academic papers, builds a knowledge graph + long-term memory, detects research communities via Leiden clustering, discovers cross-paper insights with evidence verification, and provides semantic Q&A --- all through an interactive terminal CLI with 23+ slash commands.

**The core value is not single-paper summarization** (ChatGPT already does that). It is **linking dozens of papers** into a computable knowledge network where shared concepts, method comparisons, contradictions, and research gaps surface automatically.

```
ChatGPT workflow:
    Paper A -> LLM -> summary A -> discarded
    Paper B -> LLM -> summary B -> discarded (knows nothing about A)

ReadLoop workflow:
    Paper A -> LLM -> analysis A -> knowledge graph + memory
    Paper B -> [recall A's knowledge] -> LLM -> analysis B (with A comparison)
                                                     |
                                                     v
                            "A and C share concept X, but B uses a different method"
                            "Method M was never evaluated on dataset D"
                            "3 papers form a research theme cluster"
```

## Features

### Analysis Pipeline
- **Deep paper analysis**: 11-section structured report per paper (flexible for surveys/benchmarks)
- **Smart truncation**: strips References before truncation, preserving Method/Experiments
- **Model tracking**: each analysis records which LLM produced it (`<!-- model: deepseek-chat -->`)
- **Contextual recall**: analysis of paper N benefits from knowledge extracted from papers 1..N-1
- **Image-only PDF support**: OCR extraction via PyMuPDF + pytesseract fallback for scanned papers

### Knowledge Graph
- **Structured extraction**: concepts, methods, datasets, metrics, and relationships from every paper
- **Concept canonicalization**: embedding-based merge of synonymous nodes (configurable threshold)
- **Hapax pruning**: removes single-occurrence concept noise for cleaner graph topology
- **Cross-paper edge detection**: automatic `shared_concept` edges between papers referencing the same entity
- **Leiden community detection**: with Louvain fallback if graspologic is not installed
- **Graph analysis**: god nodes, surprising cross-community connections, auto-generated research questions

### Memory System
- **Fact/claim extraction**: structured memories from each analysis with confidence scores
- **Hybrid search**: 70% embedding + 20% keyword + 10% tag, multiplicative confidence adjustment
- **Anti-amplification**: Q&A insights stored at low confidence (0.35), excluded from default retrieval, with embedding dedup at 0.92 threshold
- **Token budget**: capped context window (6000 tokens) for LLM synthesis

### Cross-Paper Synthesis (v2.2)
- **Four-stage pipeline**: digest extraction -> candidate insight generation -> evidence grounding verification -> final report
- **Grounded insights**: each cross-paper finding is verified against source paper evidence before inclusion
- **Verified insight audit trail**: `verified_insights.json` saved alongside the report

### Export & Visualization
- **Interactive HTML**: vis-network graph with sidebar, search, community coloring, type shapes, degree scaling
- **Obsidian wiki**: per-community articles, per-paper pages, concept pages with `[[wikilinks]]`
- **GraphML**: importable into Gephi, yEd, Cytoscape

### Engineering (v2.2)
- **pip installable**: `pip install -e .` with proper Python packaging
- **Setup wizard**: `readloop --init` interactive configuration (LLM keys, paper dirs, connectivity test)
- **Startup validation**: environment checks with Rich panel display at launch
- **LLM retry**: exponential backoff with jitter for transient API errors (429/timeout/5xx)
- **Structured exceptions**: `LLMError`, `ConfigError`, `PaperError`, `ExtractionError`
- **Rich progress bars**: batch analysis, memory build, graph construction
- **Unified command dispatch**: shared `commands/` subpackage eliminates code duplication between CLI and script mode

### Interactive CLI
- 23+ slash commands with Tab completion and input history
- Fuzzy command matching
- Rich terminal output (tables, trees, panels, syntax highlighting)

## Quick Start

### 1. Install

```bash
git clone https://github.com/Csh0601/readloop.git
cd readloop
pip install -e .

# Optional: Leiden community detection
pip install -e ".[leiden]"

# Optional: all extras
pip install -e ".[all]"
```

### 2. Configure

```bash
# Interactive setup wizard (recommended)
readloop --init

# Or manually:
cp .env.example .env
# Edit .env with your API keys and paper directories
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key (primary LLM) |
| `CLAUDE_API_KEY` | Claude API key (fallback LLM) |
| `REFERENCE_DIR_1` | Path to your paper PDF directory |
| `OUTPUT_DIR` | Where analysis outputs are stored |

### 3. Run

```bash
# Interactive mode (recommended)
readloop

# Alternative entry points
python -m readloop
python run.py                              # Legacy backward compat

# Script mode
readloop --list                            # List available papers
readloop --single "paper-keyword"          # Analyze one paper
readloop --build-graph                     # Build knowledge graph
readloop --ask "Which papers discuss X?"   # Semantic Q&A
readloop --help                            # All options
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | System status overview |
| `/init` | Run setup wizard |
| `/list [ref\|agent]` | List discovered papers |
| `/analyze <keyword>` | Analyze a single paper |
| `/batch [ref\|agent]` | Batch analyze papers |
| `/cross` | Four-stage cross-paper synthesis |
| `/build` | Build knowledge graph (+ canonicalize + cluster) |
| `/graph` | Show graph statistics |
| `/cluster` | Run Leiden community detection |
| `/viz` | Open interactive graph visualization |
| `/gods [n]` | Top-N most connected nodes |
| `/surprises [n]` | Cross-community surprising connections |
| `/questions [n]` | Auto-generated research questions |
| `/gaps` | Find research gaps (LLM) |
| `/build-mem` | Build memory from all analyses |
| `/memory` | Memory store statistics |
| `/ask <query>` | Semantic Q&A over knowledge base |
| `/review <topic>` | Generate literature review |
| `/track <concept>` | Track concept evolution across papers |
| `/propose [topic]` | Generate research proposals |
| `/wiki <dir>` | Export Obsidian-compatible wiki |
| `/graphml <file>` | Export GraphML |

## Architecture

```
                          +------------------+
                          |   PDF Papers     |
                          +--------+---------+
                                   |
                     +-------------v--------------+
                     |      Ingest Layer           |
                     |  reader.py  (PyMuPDF+OCR)   |
                     |  pipeline.py (orchestrator) |
                     +-------------+--------------+
                                   |
                    +--------------v---------------+
                    |      Analysis Layer           |
                    |  LLM: DeepSeek V3 / Claude    |
                    |  retry.py (exp backoff)       |
                    |  -> analysis.md               |
                    |  -> extraction.json            |
                    |  -> digest.json                |
                    +---------+----------+----------+
                              |          |
              +---------------v--+    +--v-----------------+
              | Knowledge Graph  |    | Memory System      |
              | models.py        |    | models.py          |
              | extractor.py     |    | store.py           |
              | graph.py         |    | embeddings.py      |
              | canonicalize.py  |    | search.py          |
              | cluster.py       |    | recall.py          |
              | analyze.py       |    +--------------------+
              +---------+--------+
                        |
           +------------v-------------+
           |      Export Layer         |
           | html_viz.py  (vis-net)    |
           | wiki_export.py (Obsidian) |
           | graphml_export.py (Gephi) |
           +---------------------------+
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | DeepSeek V3 (primary) + Claude Sonnet 4.6 (fallback) |
| PDF | PyMuPDF (+ pytesseract for image-only OCR) |
| Embedding | all-MiniLM-L6-v2 (22MB, 384-dim, CPU) |
| Graph algorithms | NetworkX + graspologic (Leiden) |
| Visualization | vis-network 9.1.6 |
| CLI | prompt_toolkit + Rich |
| Storage | JSON + NumPy (fully local, no database) |

## Project Structure

```
readloop/
  pyproject.toml               # pip package definition
  run.py                       # Legacy entry point (backward compat)
  .env.example                 # Configuration template
  readloop/
    __init__.py
    __main__.py                # python -m readloop support
    cli.py                     # Interactive REPL (23+ commands)
    _run.py                    # Script mode (argparse)
    client.py                  # Dual LLM client with retry
    config.py                  # All configuration from .env
    exceptions.py              # Structured exception hierarchy
    init.py                    # Setup wizard (readloop --init)
    pipeline.py                # Analysis pipeline + cross-paper synthesis
    prompts.py                 # All LLM prompts
    reader.py                  # PDF/image text extraction + OCR
    retry.py                   # Exponential backoff with jitter
    utils.py                   # Shared utilities (paper_id, entry_id)
    validate.py                # Startup environment checks
    commands/                  # Shared command implementations
      papers.py                # Paper collection, listing, lookup
      graph.py                 # Knowledge graph commands
      memory.py                # Memory system commands
      analysis.py              # Paper analysis commands
      export.py                # Wiki + GraphML export
      features.py              # Review, tracking, proposals
    knowledge/
      models.py                # Node, Edge, KnowledgeGraph dataclasses
      extractor.py             # LLM-based entity extraction
      graph.py                 # Graph construction + cross-paper edges
      canonicalize.py          # Concept merging + hapax pruning
      cluster.py               # Leiden / Louvain community detection
      analyze.py               # God nodes, surprising connections, questions
      nx_bridge.py             # KnowledgeGraph <-> NetworkX conversion
      html_viz.py              # Interactive HTML visualization
      wiki_export.py           # Obsidian vault generator
      graphml_export.py        # GraphML export
      prompts.py               # Knowledge extraction prompts
    memory/
      models.py                # MemoryEntry, MemoryStore dataclasses
      store.py                 # Memory extraction from analyses
      embeddings.py            # sentence-transformers wrapper + index
      search.py                # Hybrid search + Q&A synthesis
      recall.py                # Contextual recall for new analyses
      prompts.py               # Memory extraction + Q&A prompts
    features/
      review.py                # Literature review generation
      evolution.py             # Concept evolution tracking
      proposals.py             # Research proposal generation
  tests/
    smoke.py                   # Data consistency checks
```

## Demo Walkthrough

```bash
readloop
```

```
/list                  # See all discovered papers
/analyze "A-MEM"       # Analyze a single paper
/build                 # Build graph (extraction + canonicalize + cluster)
/graph                 # Check stats: nodes, edges, communities
/gods 10               # Core concepts across all papers
/surprises 5           # Unexpected cross-theme connections
/questions 5           # Auto-generated research questions

/build-mem             # Build memory store + embeddings
/ask What are the key differences between A-MEM and Mem0?
/ask Which papers discuss memory compression techniques?

/cross                 # 4-stage cross-paper synthesis (the core output)
/gaps                  # Research gap detection
/review "agent memory" # Literature review

/viz                   # Open interactive HTML graph
/wiki output/wiki      # Export Obsidian vault
```

## Design Decisions

**Why not a web frontend?** The CLI design is intentional: it avoids frontend complexity, enables screen recording for demos, and mirrors the workflow of tools like Claude Code.

**Why dual LLM?** DeepSeek V3 handles the majority of calls (fast, cheap). Claude Sonnet 4.6 is the fallback for when DeepSeek is unavailable. Each analysis records which model was used.

**Why local embeddings?** `all-MiniLM-L6-v2` runs on CPU with zero API cost. After first download (~22MB), it works fully offline.

**Why four-stage cross-analysis?** Direct "summarize all papers" prompts produce plausible but ungrounded insights. The verify stage filters out claims that can't be traced back to specific paper evidence.

**Why pip packaging?** `pip install -e .` makes `readloop` available as a proper CLI command, eliminates `sys.path` hacks, and enables future PyPI distribution.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `READLOOP_MERGE_THRESHOLD` | `0.90` | Cosine similarity threshold for concept merging |
| `READLOOP_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name or local path |
| `READLOOP_LLM_TRUST_ENV` | `0` | Set to `1` only if LLM API must use system proxy |
| `HF_ENDPOINT` | - | Hugging Face mirror (e.g., `https://hf-mirror.com` for China) |

## Repository Notes

This repository excludes:

- local `.env` secrets (API keys, proxy settings)
- source paper PDFs and private data folders
- generated output artifacts (embeddings, graph files, reports)

## License

MIT
