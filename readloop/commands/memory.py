"""Memory system commands."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from ..client import LLMClient
from ..config import MEMORY_DIR, OUTPUT_DIR


def cmd_build_memory(console: Console, client: LLMClient) -> None:
    """Build memory store from all analyses."""
    console.print("[bold]Building memory store...[/]")
    from ..memory.store import build_memory_from_analyses

    store, index = build_memory_from_analyses(OUTPUT_DIR, client)
    stats = store.stats()
    console.print(
        f"[green]Memory: {stats['total_entries']} entries, {len(index)} embeddings[/]"
    )


def cmd_memory_stats(console: Console) -> None:
    """Display memory store statistics."""
    from ..memory.embeddings import EmbeddingIndex
    from ..memory.models import MemoryStore

    mem_path = MEMORY_DIR / "memory_store.json"
    if not mem_path.exists():
        console.print("[red]No memory store. Run /build-mem first.[/]")
        return

    store = MemoryStore.load(mem_path)
    index = EmbeddingIndex.load(MEMORY_DIR)
    stats = store.stats()

    table = Table(title="Memory Store", border_style="dim")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="cyan", justify="right")
    table.add_row("Entries", str(stats["total_entries"]))
    table.add_row("Embeddings", str(len(index)))
    table.add_row("Papers covered", str(stats["papers_covered"]))
    for t, c in stats["type_counts"].items():
        table.add_row(f"  {t}", str(c))
    console.print(table)


def cmd_ask(console: Console, client: LLMClient, query: str) -> None:
    """Answer a question using semantic search + LLM."""
    console.print(f"[bold cyan]Q:[/] {query}\n")
    from ..memory.search import ask_with_memory

    answer = ask_with_memory(query, client)
    console.print(Markdown(answer))
