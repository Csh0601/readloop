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
from .exceptions import ExtractionError, PaperError
from .reader import extract_paper_text, get_paper_name
from .prompts import PAPER_ANALYSIS
from .config import OUTPUT_DIR, MAX_TOKENS
from .utils import safe_dirname


def _smart_truncate(text: str, max_chars: int = 60000) -> str:
    """Strip References section, then truncate middle if still too long."""
    ref_pattern = r'\n\s*(?:References|REFERENCES|Bibliography|参考文献)\s*\n'
    parts = re.split(ref_pattern, text, maxsplit=1, flags=re.IGNORECASE)
    text = parts[0]

    if len(text) > max_chars:
        head = text[:max_chars - 5000]
        tail = text[-5000:]
        text = head + "\n\n[... middle section truncated ...]\n\n" + tail
    return text


def analyze_single_paper(paper_path: Path, client: LLMClient) -> dict:
    paper_name = get_paper_name(paper_path)
    safe_name = safe_dirname(paper_name)
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
        raise PaperError(f"No text extracted from {paper_path}")

    text = _smart_truncate(text)

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
    analysis, model_used = client.chat_with_meta(prompt, max_tokens=MAX_TOKENS)
    analysis = f"<!-- model: {model_used} -->\n{analysis}"

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
    """Post-analysis extraction: knowledge graph entities + digest for cross-analysis."""
    import json
    from .prompts import EXTRACT_PAPER_DIGEST

    # 1. Structured extraction for knowledge graph
    extraction_path = output_path / "extraction.json"
    if not extraction_path.exists():
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
            try:
                error_log = OUTPUT_DIR / "_errors.log"
                from datetime import datetime
                with open(error_log, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] {paper_name}: {e}\n")
            except Exception:
                pass

    # 2. Paper digest for cross-analysis (compact structured summary)
    digest_path = output_path / "digest.json"
    if not digest_path.exists():
        try:
            console.print("  [dim]generating digest...[/]")
            digest = client.chat_json(
                EXTRACT_PAPER_DIGEST.format(analysis_text=analysis[:20000]),
                max_tokens=1500,
            )
            digest_path.write_text(
                json.dumps(digest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            console.print(f"  [dim]digest skipped: {e}[/]")


def analyze_all_papers(paper_paths: list[Path], client: LLMClient) -> list[dict]:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    results = []
    total = len(paper_paths)
    failed = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing papers", total=total)
        for path in paper_paths:
            name = get_paper_name(path)
            progress.update(task, description=f"[cyan]{name[:50]}[/]")
            try:
                results.append(analyze_single_paper(path, client))
            except Exception as e:
                console.print(f"  [bold red]FAIL: {name[:50]} -- {e}[/]")
                failed.append((name, str(e)))
                results.append({
                    "name": name, "output_path": None,
                    "summary": f"failed: {e}", "analysis": "",
                })
            progress.advance(task)

    if failed:
        console.print(f"\n[bold red]Failed ({len(failed)}/{total}):[/]")
        for name, err in failed:
            console.print(f"  - {name[:50]}: {err[:80]}")

    return results


def generate_cross_analysis(results: list[dict], client: LLMClient) -> Path:
    """跨论文综合分析 -- Harness 核心价值

    Four-stage pipeline:
    A. Load/generate per-paper digests (compact structured summaries)
    B. Generate candidate cross-paper insights
    C. Verify each insight against cited evidence
    D. Generate final report based on verified insights only
    """
    import json
    from .prompts import CROSS_ANALYSIS_STAGE_A, CROSS_ANALYSIS_VERIFY, CROSS_ANALYSIS_FINAL

    output_path = OUTPUT_DIR / "00_cross_analysis"
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "cross_analysis.md"

    if report_path.exists():
        console.print("[dim]skip: cross analysis exists[/]")
        return report_path

    console.print("[bold magenta]>>> CROSS-PAPER ANALYSIS (harness core)[/]")

    successful = [r for r in results if r["analysis"]]

    # --- Stage A: Load digests ---
    console.print("  [dim]Stage A: loading paper digests...[/]")
    digests: dict[str, dict] = {}
    for r in successful:
        paper_name = r.get("name", "unknown")
        output_dir = r.get("output_path")
        digest_path = Path(output_dir) / "digest.json" if output_dir else None
        if digest_path and digest_path.exists():
            try:
                digests[paper_name] = json.loads(digest_path.read_text(encoding="utf-8"))
                continue
            except json.JSONDecodeError as e:
                console.print(f"  [yellow]digest unreadable for {paper_name}: {e}[/]")

        analysis_text = r.get("analysis", "")
        digests[paper_name] = {
            "title": paper_name,
            "one_liner": r.get("summary") or paper_name,
            "method": analysis_text[:2000],
        }

    digest_blob = json.dumps(digests, ensure_ascii=False, indent=2)

    # --- Stage B: Generate candidate insights ---
    console.print("  [dim]Stage B: generating candidate insights...[/]")
    try:
        candidates = client.chat_json(
            CROSS_ANALYSIS_STAGE_A.format(count=len(successful), digests=digest_blob),
            max_tokens=4000,
        )
    except Exception as e:
        console.print(f"  [yellow]Stage B failed ({e}), falling back to legacy mode[/]")
        return _generate_cross_analysis_legacy(successful, client, output_path, report_path)

    insights = candidates.get("insights", [])
    console.print(f"  [dim]{len(insights)} candidate insights generated[/]")

    # --- Stage C: Verify grounding ---
    console.print("  [dim]Stage C: verifying evidence grounding...[/]")
    verified = []
    for ins in insights:
        cited_papers = ins.get("evidence_papers", [])
        cited_digests = {p: digests[p] for p in cited_papers if p in digests}
        if not cited_digests:
            if cited_papers:
                console.print(
                    f"  [yellow]skipped insight: no matching digests for {cited_papers}[/]"
                )
            continue
        try:
            verdict = client.chat_json(
                CROSS_ANALYSIS_VERIFY.format(
                    claim=ins["claim"],
                    evidence=json.dumps(cited_digests, ensure_ascii=False),
                ),
                max_tokens=500,
            )
            if verdict.get("grounded", False):
                ins["verified"] = True
                ins["ground_reason"] = verdict.get("reason", "")
                verified.append(ins)
        except Exception:
            continue

    console.print(f"  [dim]{len(verified)}/{len(insights)} insights verified[/]")

    # --- Stage D: Final report ---
    console.print("  [dim]Stage D: generating final report...[/]")
    prompt = CROSS_ANALYSIS_FINAL.format(
        count=len(successful),
        digests=digest_blob,
        verified_insights=json.dumps(verified, ensure_ascii=False, indent=2),
    )
    analysis = client.chat(prompt, max_tokens=MAX_TOKENS)
    report_path.write_text(analysis, encoding="utf-8")

    # Save verification results for auditing
    (output_path / "verified_insights.json").write_text(
        json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = len(analysis.split("\n"))
    console.print(f"[bold green]done ({lines} lines, {len(verified)} verified insights): 00_cross_analysis/[/]")
    return report_path


def _generate_cross_analysis_legacy(
    successful: list[dict], client: LLMClient, output_path: Path, report_path: Path
) -> Path:
    """Legacy fallback: direct analysis without digest/verification pipeline."""
    from .prompts import CROSS_ANALYSIS
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
    console.print(f"[bold green]done ({lines} lines, legacy mode): 00_cross_analysis/[/]")
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
