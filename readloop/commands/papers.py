"""Paper collection, listing, and lookup."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..config import REFERENCE_DIRS, OUTPUT_DIR
from ..reader import get_paper_name


def collect_papers(
    source: str | None = None,
    category: str | None = None,
) -> list[tuple[str, Path]]:
    """Collect paper paths from reference directories.

    Args:
        source: "ref" or "agent" to filter, None for both.
        category: "A", "B", "C" prefix filter for agent papers.
    """
    ref_dir = REFERENCE_DIRS[0] if len(REFERENCE_DIRS) > 0 else None
    agent_dir = REFERENCE_DIRS[1] if len(REFERENCE_DIRS) > 1 else None

    results: list[tuple[str, Path]] = []
    if source != "agent" and ref_dir and ref_dir.exists():
        for d in sorted(ref_dir.iterdir()):
            if d.is_dir():
                results.append(("ref", d))
            elif d.suffix == ".pdf":
                results.append(("ref", d))

    if source != "ref" and agent_dir and agent_dir.exists():
        for cat_dir in sorted(agent_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            if category and not cat_dir.name.startswith(category):
                continue
            for pdf in sorted(cat_dir.glob("*.pdf")):
                results.append(("agent", pdf))

    return results


def list_papers(
    console: Console,
    source: str | None = None,
    category: str | None = None,
) -> None:
    """Display available papers in a Rich table."""
    papers = collect_papers(source, category)

    table = Table(title=f"Papers ({len(papers)})", border_style="dim")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Src", style="magenta", width=5)
    table.add_column("Name", style="white")
    table.add_column("Fmt", style="green", width=8)

    for i, (src, path) in enumerate(papers, 1):
        if path.is_file() and path.suffix == ".pdf":
            name, fmt = path.stem, "PDF"
        else:
            name = get_paper_name(path)
            fmt = "PDF+IMG" if list(path.glob("*.pdf")) else "IMG"
        table.add_row(str(i), src, name[:65], fmt)

    console.print(table)


def find_paper(keyword: str) -> tuple[str, Path] | None:
    """Find a paper by case-insensitive keyword match."""
    for src, path in collect_papers():
        name = path.stem if path.is_file() else path.name
        if keyword.lower() in name.lower():
            return src, path
    return None


def load_existing_results() -> list[dict]:
    """Load all existing analysis results from output directory."""
    results: list[dict] = []
    if not OUTPUT_DIR.exists():
        return results
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("00_"):
            continue
        report = d / "analysis.md"
        if report.exists():
            analysis = report.read_text(encoding="utf-8")
            results.append({
                "name": d.name,
                "output_path": d,
                "summary": d.name,
                "analysis": analysis,
            })
    return results
