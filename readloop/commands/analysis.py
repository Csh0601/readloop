"""Paper analysis commands (single, batch, cross-paper)."""
from __future__ import annotations

from rich.console import Console

from ..client import LLMClient
from ..config import OUTPUT_DIR


def cmd_analyze(console: Console, client: LLMClient, keyword: str) -> dict | None:
    """Find and analyze a single paper by keyword match."""
    from .papers import find_paper

    match = find_paper(keyword)
    if not match:
        console.print(f"[red]Paper not found: '{keyword}'[/]")
        return None

    _, path = match
    console.print(f"[bold]Analyzing: {path.name}[/]")

    from ..pipeline import analyze_single_paper

    result = analyze_single_paper(path, client)
    if result.get("analysis"):
        lines = result["analysis"].count("\n") + 1
        console.print(f"[green]Done ({lines} lines) -> {result.get('output_path', '')}[/]")
    else:
        console.print("[red]Analysis failed[/]")
    return result


def cmd_batch(
    console: Console,
    client: LLMClient,
    source: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Batch analyze papers with automatic cross-paper analysis."""
    from .papers import collect_papers
    from ..pipeline import analyze_all_papers, generate_cross_analysis

    papers = collect_papers(source, category)
    if not papers:
        console.print("[red]No papers found[/]")
        return []

    paths = [p for _, p in papers]
    console.print(f"[bold]Batch analyzing {len(paths)} papers...[/]")
    results = analyze_all_papers(paths, client)
    successful = [r for r in results if r.get("analysis")]
    console.print(f"[green]Analyzed: {len(successful)}/{len(paths)}[/]")

    if len(successful) >= 2:
        console.print("[bold]Running cross-paper analysis...[/]")
        generate_cross_analysis(successful, client)
        console.print("[green]Cross-analysis saved[/]")

    return results


def cmd_cross(console: Console, client: LLMClient) -> None:
    """Run cross-paper analysis on existing results."""
    from .papers import load_existing_results
    from ..pipeline import generate_cross_analysis

    results = load_existing_results()
    if len(results) < 2:
        console.print(f"[red]Need 2+ analyses, found {len(results)}[/]")
        return

    console.print(f"[bold]Cross-analyzing {len(results)} papers...[/]")
    generate_cross_analysis(results, client)
    console.print("[green]Cross-analysis saved[/]")
