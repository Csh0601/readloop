"""Startup environment validation — checks API keys, paths, and dependencies."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def validate_environment(console: Console | None = None) -> bool:
    """Run all validation checks. Returns True if system is usable.

    Prints a Rich panel with pass/warn/fail for each check.
    """
    if console is None:
        console = Console(force_terminal=True)

    from .config import (
        CLAUDE_API_KEY, DEEPSEEK_API_KEY,
        REFERENCE_DIRS, OUTPUT_DIR,
    )

    checks: list[tuple[str, str, str]] = []  # (status_icon, name, detail)
    has_critical_failure = False

    # 1. LLM API keys
    has_deepseek = bool(DEEPSEEK_API_KEY)
    has_claude = bool(CLAUDE_API_KEY)
    if has_deepseek and has_claude:
        checks.append(("✓", "LLM backends", "DeepSeek (primary) + Claude (fallback)"))
    elif has_deepseek:
        checks.append(("✓", "LLM backends", "DeepSeek only (no fallback)"))
    elif has_claude:
        checks.append(("✓", "LLM backends", "Claude only (no fallback)"))
    else:
        checks.append(("✗", "LLM backends", "No API key! Set DEEPSEEK_API_KEY or CLAUDE_API_KEY in .env"))
        has_critical_failure = True

    # 2. Paper directories
    found_papers = False
    for ref_dir in REFERENCE_DIRS:
        if ref_dir.exists():
            pdf_count = sum(1 for _ in ref_dir.rglob("*.pdf"))
            if pdf_count > 0:
                checks.append(("✓", f"Papers ({ref_dir.name})", f"{pdf_count} PDFs in {ref_dir}"))
                found_papers = True
            else:
                checks.append(("~", f"Papers ({ref_dir.name})", f"Directory exists but no PDFs: {ref_dir}"))
        else:
            checks.append(("~", f"Papers ({ref_dir.name})", f"Not found: {ref_dir}"))

    if not found_papers:
        checks.append(("~", "Papers", "No PDF papers found. Add PDFs to a REFERENCE_DIR or use /fetch"))

    # 3. Output directory
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        checks.append(("✓", "Output directory", str(OUTPUT_DIR)))
    except OSError as e:
        checks.append(("✗", "Output directory", f"Cannot create {OUTPUT_DIR}: {e}"))
        has_critical_failure = True

    # 4. Embedding model
    try:
        from sentence_transformers import SentenceTransformer
        checks.append(("✓", "Embedding model", "sentence-transformers available"))
    except ImportError:
        checks.append(("✗", "Embedding model", "pip install sentence-transformers"))
        has_critical_failure = True

    # 5. Optional: graspologic for Leiden
    try:
        import graspologic  # noqa: F401
        checks.append(("✓", "Community detection", "Leiden (graspologic)"))
    except ImportError:
        checks.append(("~", "Community detection", "Louvain fallback (pip install graspologic for Leiden)"))

    # Build display
    lines = Text()
    for icon, name, detail in checks:
        if icon == "✓":
            lines.append(f"  {icon} ", style="green")
        elif icon == "✗":
            lines.append(f"  {icon} ", style="bold red")
        else:
            lines.append(f"  {icon} ", style="yellow")
        lines.append(f"{name}: ", style="bold")
        lines.append(f"{detail}\n")

    title = "[red]Environment Check FAILED[/]" if has_critical_failure else "[green]Environment Check OK[/]"
    console.print(Panel(lines, title=title, border_style="dim"))

    return not has_critical_failure
