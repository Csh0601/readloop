# ReadLoop

ReadLoop is an interactive paper-research harness that turns a set of papers into reusable knowledge assets:

- per-paper structured analyses
- a cross-paper knowledge graph
- a long-term memory store with embeddings
- semantic Q&A, literature review, concept tracking, and proposal generation
- interactive HTML visualization and export tools

## Features

- Interactive CLI with 24 slash commands
- Paper analysis from local PDF collections
- Knowledge graph construction with concept canonicalization and community detection
- Long-term memory extraction with embedding search
- Cross-paper synthesis with candidate generation and evidence verification
- Export to HTML, Obsidian-style wiki, and GraphML

## Quick Start

```powershell
cd D:\wu\readloop
pip install -r requirements.txt
copy .env.example .env
python run.py
```

## Main Commands

- `/status` — inspect system state
- `/list` — list discovered papers
- `/analyze <keyword>` — analyze one paper
- `/build` — build the knowledge graph
- `/cluster` — run community detection
- `/build-mem` — build memory + embeddings
- `/ask <question>` — query the knowledge base
- `/cross` — run cross-paper synthesis
- `/viz` — open the interactive graph view

## Repository Notes

This repository excludes:

- local `.env` secrets
- source paper PDFs and private data folders
- generated output artifacts such as embeddings, graph files, and reports

See `docs/ARCHITECTURE.md` and `docs/ARCHITECTURE_MODIFICATION_REPORT.md` for detailed design and current-state notes.
