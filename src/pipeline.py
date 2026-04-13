"""核心分析管道 -- Claude Sonnet 4.6 深度论文分析"""
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console

console = Console(force_terminal=True)

from .client import LLMClient
from .reader import extract_paper_text, get_paper_name
from .prompts import PAPER_ANALYSIS, CROSS_ANALYSIS
from .config import OUTPUT_DIR, MAX_TOKENS


def _safe_dirname(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name[:80]).strip()


def analyze_single_paper(paper_path: Path, client: LLMClient) -> dict:
    paper_name = get_paper_name(paper_path)
    safe_name = _safe_dirname(paper_name)
    output_path = OUTPUT_DIR / safe_name
    output_path.mkdir(parents=True, exist_ok=True)

    report_path = output_path / "analysis.md"
    if report_path.exists():
        console.print(f"  [dim]skip: {paper_name[:60]}[/]")
        analysis = report_path.read_text(encoding="utf-8")
        return {
            "name": paper_name,
            "output_path": output_path,
            "summary": _extract_summary(analysis, paper_name),
            "analysis": analysis,
        }

    console.print(f"[bold cyan]>>> {paper_name[:70]}[/]")

    console.print("  [dim]extracting text...[/]")
    fmt, text = extract_paper_text(paper_path)
    if not text.strip():
        raise ValueError(f"No text extracted from {paper_path}")

    # Truncate long papers, keeping structure
    if len(text) > 60000:
        head = text[:45000]
        tail = text[-12000:]
        text = head + "\n\n[... middle truncated ...]\n\n" + tail

    # Contextual recall: inject relevant prior knowledge if available
    recall_context = ""
    try:
        from .memory.recall import get_recall_context
        recall_context = get_recall_context(text[:2000])
        if recall_context:
            console.print("  [dim]injected prior knowledge from memory[/]")
    except Exception:
        pass  # memory not built yet, skip

    console.print("  [dim]LLM analyzing...[/]")
    prompt = recall_context + PAPER_ANALYSIS.format(paper_text=text, paper_title=paper_name)
    analysis = client.chat(prompt, max_tokens=MAX_TOKENS)

    report_path.write_text(analysis, encoding="utf-8")
    lines = len(analysis.split("\n"))
    console.print(f"  [bold green]done ({lines} lines)[/]")

    # Post-analysis: extract structured data for knowledge graph + memory
    _post_extract(output_path, analysis, paper_name, client)

    return {
        "name": paper_name,
        "output_path": output_path,
        "summary": _extract_summary(analysis, paper_name),
        "analysis": analysis,
    }


def _post_extract(output_path: Path, analysis: str, paper_name: str, client: LLMClient) -> None:
    """Post-analysis extraction: knowledge graph entities + memory entries."""
    import json

    extraction_path = output_path / "extraction.json"
    if extraction_path.exists():
        return  # already extracted

    try:
        console.print("  [dim]extracting structured data...[/]")
        from .knowledge.extractor import extract_from_analysis
        extraction = extract_from_analysis(analysis, paper_name, client)
        extraction_path.write_text(
            json.dumps(extraction, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        console.print(f"  [dim]extraction skipped: {e}[/]")


def analyze_all_papers(paper_paths: list[Path], client: LLMClient) -> list[dict]:
    results = []
    total = len(paper_paths)
    failed = []

    for i, path in enumerate(paper_paths, 1):
        console.print(f"\n[bold]=== [{i}/{total}] ===[/]")
        try:
            results.append(analyze_single_paper(path, client))
        except Exception as e:
            name = get_paper_name(path)
            console.print(f"  [bold red]FAIL: {name[:50]} -- {e}[/]")
            failed.append((name, str(e)))
            results.append({
                "name": name, "output_path": None,
                "summary": f"failed: {e}", "analysis": "",
            })

    if failed:
        console.print(f"\n[bold red]Failed ({len(failed)}/{total}):[/]")
        for name, err in failed:
            console.print(f"  - {name[:50]}: {err[:80]}")

    return results


def generate_cross_analysis(results: list[dict], client: LLMClient) -> Path:
    """跨论文综合分析 -- Harness 核心价值"""
    output_path = OUTPUT_DIR / "00_cross_analysis"
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "cross_analysis.md"

    if report_path.exists():
        console.print("[dim]skip: cross analysis exists[/]")
        return report_path

    console.print("[bold magenta]>>> CROSS-PAPER ANALYSIS (harness core)[/]")

    successful = [r for r in results if r["analysis"]]
    per_paper = min(3000, 65000 // max(len(successful), 1))

    summaries_parts = []
    for i, r in enumerate(successful, 1):
        summaries_parts.append(f"### Paper {i}: {r['name']}\n{r['analysis'][:per_paper]}\n")

    prompt = CROSS_ANALYSIS.format(
        count=len(successful),
        papers_summaries="\n".join(summaries_parts),
    )

    analysis = client.chat(prompt, max_tokens=MAX_TOKENS)
    report_path.write_text(analysis, encoding="utf-8")

    lines = len(analysis.split("\n"))
    console.print(f"[bold green]done ({lines} lines): 00_cross_analysis/[/]")
    return report_path


def _extract_summary(analysis: str, paper_name: str) -> str:
    lines = analysis.split("\n")
    for i, line in enumerate(lines):
        if "一句话" in line and ("定位" in line or "总结" in line):
            for next_line in lines[i + 1 : i + 5]:
                stripped = next_line.strip().lstrip("> ")
                if stripped and not stripped.startswith("#"):
                    return stripped
    return paper_name
