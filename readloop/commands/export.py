"""Export commands (Obsidian wiki, GraphML)."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ..config import GRAPH_DIR, OUTPUT_DIR


def _safe_output_path(user_input: str, base: Path) -> Path:
    """Resolve user-supplied path, ensuring it stays within base directory."""
    resolved = (base / user_input).resolve()
    base_resolved = base.resolve()
    if not resolved.is_relative_to(base_resolved):
        raise ValueError(f"Path escapes allowed directory: {resolved}")
    return resolved


def cmd_export_wiki(console: Console, output_dir: str | None = None) -> None:
    """Export knowledge graph to Obsidian wiki."""
    from ..knowledge.models import KnowledgeGraph
    from ..knowledge.wiki_export import to_wiki

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return

    if output_dir:
        out_path = _safe_output_path(output_dir, OUTPUT_DIR)
    else:
        out_path = OUTPUT_DIR / "wiki"

    count = to_wiki(graph, communities, out_path)
    console.print(f"[green]Exported {count} wiki articles -> {out_path}[/]")


def cmd_export_graphml(console: Console, output_file: str | None = None) -> None:
    """Export knowledge graph to GraphML format."""
    from ..knowledge.models import KnowledgeGraph
    from ..knowledge.graphml_export import to_graphml

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")

    if output_file:
        out_path = _safe_output_path(output_file, OUTPUT_DIR)
    else:
        out_path = GRAPH_DIR / "graph.graphml"

    to_graphml(graph, out_path)
    console.print(f"[green]Saved: {out_path}[/]")
