"""记忆存储 -- 从 analysis.md 提取 + 持久化"""
from __future__ import annotations

from pathlib import Path

from ..client import LLMClient
from ..config import MEMORY_DIR
from ..utils import make_entry_id, make_paper_id
from .models import MemoryStore, MemoryEntry
from .embeddings import EmbeddingIndex
from .prompts import EXTRACT_MEMORIES


def _make_id(content: str, paper: str) -> str:
    """Deterministic ID from content + paper."""
    return make_entry_id("mem", content, paper)


def extract_memories_from_analysis(
    analysis_text: str,
    paper_name: str,
    client: LLMClient,
) -> list[MemoryEntry]:
    """Extract memory entries from an analysis.md using LLM."""
    if len(analysis_text) > 40000:
        analysis_text = analysis_text[:40000]

    prompt = EXTRACT_MEMORIES.format(
        analysis_text=analysis_text,
        paper_name=paper_name,
    )
    data = client.chat_json(prompt, max_tokens=4000)

    entries = []
    for fact in data.get("facts", []):
        entries.append(MemoryEntry(
            id=_make_id(fact["content"], paper_name),
            type="fact",
            content=fact["content"],
            source_papers=[paper_name],
            domain_tags=fact.get("tags", []),
            confidence=1.0,
        ))
    for claim in data.get("claims", []):
        entries.append(MemoryEntry(
            id=_make_id(claim["content"], paper_name),
            type="claim",
            content=claim["content"],
            source_papers=[paper_name],
            domain_tags=claim.get("tags", []),
            confidence=claim.get("confidence", 0.8),
        ))
    return entries


def build_memory_from_analyses(
    output_dir: Path,
    client: LLMClient,
) -> tuple[MemoryStore, EmbeddingIndex]:
    """Build full memory store + embedding index from all analyses."""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    console = Console(force_terminal=True)
    store_path = MEMORY_DIR / "memory_store.json"
    store = MemoryStore()
    index = EmbeddingIndex()

    batch_entries: list[tuple[str, str]] = []

    paper_dirs = [
        d for d in sorted(output_dir.iterdir())
        if d.is_dir() and not d.name.startswith("00_") and (d / "analysis.md").exists()
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting memories", total=len(paper_dirs))
        for paper_dir in paper_dirs:
            paper_id = make_paper_id(paper_dir.name)
            progress.update(task, description=f"[cyan]{paper_id[:50]}[/]")
            analysis = (paper_dir / "analysis.md").read_text(encoding="utf-8")

            try:
                entries = extract_memories_from_analysis(analysis, paper_id, client)
            except Exception as e:
                console.print(f"  [red]failed: {paper_id[:40]}: {e}[/]")
                progress.advance(task)
                continue

            for entry in entries:
                store.add(entry)
                batch_entries.append((entry.id, entry.content))

            progress.advance(task)

    # Build embeddings in batch
    if batch_entries:
        console.print(f"  [dim]Building embeddings for {len(batch_entries)} entries...[/]")
        index.add_batch(batch_entries)

    store.save(store_path)
    index.save(MEMORY_DIR)

    return store, index
