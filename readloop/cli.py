"""ReadLoop Interactive CLI -- research tool with slash commands.

Usage:
    readloop          # Launch interactive mode
    readloop --help   # Script mode arguments
"""
from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .config import (
    GRAPH_DIR, MEMORY_DIR, OUTPUT_DIR,
    REFERENCE_DIRS, DEEPSEEK_MODEL, CLAUDE_MODEL,
)

console = Console(force_terminal=True)

VERSION = "2.2.0"

COMMANDS: dict[str, dict] = {
    "/help":       {"args": "",              "desc": "Show this help"},
    "/status":     {"args": "",              "desc": "System status (graph, memory, papers)"},
    "/list":       {"args": "[ref|agent]",   "desc": "List available papers"},
    "/analyze":    {"args": "<keyword>",     "desc": "Analyze a single paper"},
    "/batch":      {"args": "[ref|agent] [A|B|C]", "desc": "Batch analyze papers"},
    "/cross":      {"args": "",              "desc": "Run cross-paper analysis"},
    "/build":      {"args": "",              "desc": "Build knowledge graph (+ auto cluster)"},
    "/graph":      {"args": "",              "desc": "Show graph statistics"},
    "/cluster":    {"args": "",              "desc": "Run community detection"},
    "/viz":        {"args": "",              "desc": "Open interactive graph in browser"},
    "/gods":       {"args": "[n]",           "desc": "Top-N most connected nodes"},
    "/surprises":  {"args": "[n]",           "desc": "Cross-community surprising connections"},
    "/questions":  {"args": "[n]",           "desc": "Generate research questions"},
    "/gaps":       {"args": "",              "desc": "Find research gaps (LLM)"},
    "/memory":     {"args": "",              "desc": "Memory store statistics"},
    "/build-mem":  {"args": "",              "desc": "Build memory from analyses"},
    "/ask":        {"args": "<query>",       "desc": "Ask a question (semantic search + LLM)"},
    "/review":     {"args": "<topic>",       "desc": "Generate literature review"},
    "/track":      {"args": "<concept>",     "desc": "Track concept evolution"},
    "/propose":    {"args": "[topic]",       "desc": "Generate research proposals"},
    "/wiki":       {"args": "<dir>",         "desc": "Export Obsidian wiki"},
    "/graphml":    {"args": "<file>",        "desc": "Export GraphML"},
    "/init":       {"args": "",              "desc": "Run setup wizard"},
    "/clear":      {"args": "",              "desc": "Clear screen"},
    "/quit":       {"args": "",              "desc": "Exit ReadLoop"},
}

COMMAND_NAMES = list(COMMANDS.keys())


# ──────────────────────────────────────────────
# Welcome / Help / Status (CLI-only)
# ──────────────────────────────────────────────

def _welcome():
    banner = Text()
    banner.append("  ReadLoop", style="bold cyan")
    banner.append(f" v{VERSION}", style="dim")
    banner.append(" -- Agent Harness for Paper Research\n", style="white")
    banner.append("  Type ", style="dim")
    banner.append("/help", style="bold yellow")
    banner.append(" to see commands, ", style="dim")
    banner.append("/quit", style="bold yellow")
    banner.append(" to exit", style="dim")
    console.print(Panel(banner, border_style="cyan", padding=(0, 1)))
    console.print()


def _show_help():
    table = Table(title="Commands", show_header=True, header_style="bold cyan",
                  border_style="dim", pad_edge=False)
    table.add_column("Command", style="yellow", min_width=14)
    table.add_column("Args", style="dim", min_width=18)
    table.add_column("Description", style="white")
    for cmd, info in COMMANDS.items():
        table.add_row(cmd, info["args"], info["desc"])
    console.print(table)


def _show_status():
    tree = Tree("[bold cyan]ReadLoop Status", guide_style="dim")

    papers_branch = tree.add("[bold]Papers")
    for ref_dir in REFERENCE_DIRS:
        if ref_dir.exists():
            count = sum(1 for x in ref_dir.iterdir() if x.is_dir() or x.suffix == ".pdf")
            papers_branch.add(f"{ref_dir.name}: {count} items")
        else:
            papers_branch.add(f"{ref_dir.name}: [red]not found[/]")

    analysis_branch = tree.add("[bold]Analyses")
    if OUTPUT_DIR.exists():
        analyzed = [d for d in OUTPUT_DIR.iterdir()
                    if d.is_dir() and not d.name.startswith("00_") and (d / "analysis.md").exists()]
        analysis_branch.add(f"{len(analyzed)} papers analyzed")
        cross = OUTPUT_DIR / "00_cross_analysis" / "cross_analysis.md"
        analysis_branch.add(f"Cross-analysis: {'[green]yes[/]' if cross.exists() else '[dim]no[/]'}")
    else:
        analysis_branch.add("[dim]No output directory[/]")

    graph_branch = tree.add("[bold]Knowledge Graph")
    graph_path = GRAPH_DIR / "graph.json"
    if graph_path.exists():
        from .knowledge.models import KnowledgeGraph
        graph = KnowledgeGraph.load(graph_path)
        stats = graph.stats()
        communities = graph.get_communities()
        graph_branch.add(f"{stats['total_nodes']} nodes, {stats['total_edges']} edges")
        graph_branch.add(f"{len(communities)} communities")
        for t, c in stats["node_types"].items():
            graph_branch.add(f"  {t}: {c}")
    else:
        graph_branch.add("[dim]Not built -- use /build[/]")

    mem_branch = tree.add("[bold]Memory")
    mem_path = MEMORY_DIR / "memory_store.json"
    if mem_path.exists():
        from .memory.models import MemoryStore
        from .memory.embeddings import EmbeddingIndex
        store = MemoryStore.load(mem_path)
        index = EmbeddingIndex.load(MEMORY_DIR)
        stats = store.stats()
        mem_branch.add(f"{stats['total_entries']} entries, {len(index)} embeddings")
        mem_branch.add(f"{stats['papers_covered']} papers covered")
    else:
        mem_branch.add("[dim]Not built -- use /build-mem[/]")

    model_branch = tree.add("[bold]LLM Config")
    model_branch.add(f"Primary: {DEEPSEEK_MODEL}")
    model_branch.add(f"Fallback: {CLAUDE_MODEL}")
    console.print(tree)


# ──────────────────────────────────────────────
# Lazy client
# ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_client():
    from .client import LLMClient
    return LLMClient()


# ──────────────────────────────────────────────
# Thin command wrappers (arg parsing only)
# ──────────────────────────────────────────────

def _cmd_list(args: str):
    from .commands.papers import list_papers
    source = args.strip() if args.strip() in ("ref", "agent") else None
    list_papers(console, source)


def _cmd_analyze(args: str):
    keyword = args.strip()
    if not keyword:
        console.print("[red]Usage: /analyze <keyword>[/]")
        return
    from .commands.analysis import cmd_analyze
    cmd_analyze(console, _get_client(), keyword)


def _cmd_batch(args: str):
    parts = args.strip().split()
    source = parts[0] if parts and parts[0] in ("ref", "agent") else None
    category = parts[1] if len(parts) > 1 and parts[1] in ("A", "B", "C") else None
    from .commands.analysis import cmd_batch
    cmd_batch(console, _get_client(), source, category)


def _cmd_cross(_args: str):
    from .commands.analysis import cmd_cross
    cmd_cross(console, _get_client())


def _cmd_build(_args: str):
    from .commands.graph import cmd_build_graph
    cmd_build_graph(console, _get_client())


def _cmd_graph(_args: str):
    from .commands.graph import cmd_show_graph
    cmd_show_graph(console)


def _cmd_cluster(_args: str):
    from .commands.graph import cmd_cluster
    cmd_cluster(console)


def _cmd_viz(_args: str):
    from .commands.graph import cmd_viz_graph
    cmd_viz_graph(console)


def _cmd_gods(args: str):
    from .commands.graph import cmd_gods
    n = int(args.strip()) if args.strip().isdigit() else 10
    cmd_gods(console, n)


def _cmd_surprises(args: str):
    from .commands.graph import cmd_surprises
    n = int(args.strip()) if args.strip().isdigit() else 5
    cmd_surprises(console, n)


def _cmd_questions(args: str):
    from .commands.graph import cmd_questions
    n = int(args.strip()) if args.strip().isdigit() else 7
    cmd_questions(console, n)


def _cmd_gaps(_args: str):
    from .commands.graph import cmd_gaps
    cmd_gaps(console, _get_client())


def _cmd_memory(_args: str):
    from .commands.memory import cmd_memory_stats
    cmd_memory_stats(console)


def _cmd_build_mem(_args: str):
    from .commands.memory import cmd_build_memory
    cmd_build_memory(console, _get_client())


def _cmd_ask(args: str):
    query = args.strip()
    if not query:
        console.print("[red]Usage: /ask <your question>[/]")
        return
    from .commands.memory import cmd_ask
    cmd_ask(console, _get_client(), query)


def _cmd_review(args: str):
    topic = args.strip()
    if not topic:
        console.print("[red]Usage: /review <topic>[/]")
        return
    from .commands.features import cmd_review
    cmd_review(console, _get_client(), topic)


def _cmd_track(args: str):
    concept = args.strip()
    if not concept:
        console.print("[red]Usage: /track <concept name>[/]")
        return
    from .commands.features import cmd_track_concept
    cmd_track_concept(console, _get_client(), concept)


def _cmd_propose(args: str):
    from .commands.features import cmd_propose
    topic = args.strip() or None
    cmd_propose(console, _get_client(), topic)


def _cmd_init(_args: str):
    from .init import run_init
    run_init(console)


def _cmd_wiki(args: str):
    from .commands.export import cmd_export_wiki
    cmd_export_wiki(console, args.strip() or None)


def _cmd_graphml(args: str):
    from .commands.export import cmd_export_graphml
    cmd_export_graphml(console, args.strip() or None)


# ──────────────────────────────────────────────
# Command dispatch
# ──────────────────────────────────────────────

DISPATCH: dict[str, Callable[[str], None]] = {
    "/help":      lambda a: _show_help(),
    "/status":    lambda a: _show_status(),
    "/list":      _cmd_list,
    "/analyze":   _cmd_analyze,
    "/batch":     _cmd_batch,
    "/cross":     _cmd_cross,
    "/build":     _cmd_build,
    "/graph":     _cmd_graph,
    "/cluster":   _cmd_cluster,
    "/viz":       _cmd_viz,
    "/gods":      _cmd_gods,
    "/surprises": _cmd_surprises,
    "/questions": _cmd_questions,
    "/gaps":      _cmd_gaps,
    "/memory":    _cmd_memory,
    "/build-mem": _cmd_build_mem,
    "/ask":       _cmd_ask,
    "/review":    _cmd_review,
    "/track":     _cmd_track,
    "/propose":   _cmd_propose,
    "/init":      _cmd_init,
    "/wiki":      _cmd_wiki,
    "/graphml":   _cmd_graphml,
}


def _parse_and_run(line: str) -> bool:
    """Parse a command line and execute. Returns False to quit."""
    line = line.strip()
    if not line:
        return True

    if line in ("/quit", "/exit", "/q"):
        return False

    if line == "/clear":
        console.clear()
        return True

    parts = line.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd not in DISPATCH:
        matches = [c for c in COMMAND_NAMES if c.startswith(cmd)]
        if len(matches) == 1:
            cmd = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Ambiguous: {', '.join(matches)}[/]")
            return True
        else:
            console.print(f"[red]Unknown command: {cmd}. Type /help[/]")
            return True

    handler = DISPATCH[cmd]
    try:
        handler(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")

    return True


# ──────────────────────────────────────────────
# Input (prompt_toolkit with fallback)
# ──────────────────────────────────────────────

def _make_prompt_session():
    """Create a prompt_toolkit session with autocomplete, or return None."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.styles import Style

        history_path = Path.home() / ".readloop_history"
        completer = WordCompleter(COMMAND_NAMES, sentence=True)
        style = Style.from_dict({"prompt": "ansicyan bold"})
        return PromptSession(
            history=FileHistory(str(history_path)),
            completer=completer,
            style=style,
            complete_while_typing=True,
        )
    except ImportError:
        return None


def run_interactive():
    """Main entry point for the interactive CLI."""
    _welcome()

    from .validate import validate_environment
    validate_environment(console)

    session = _make_prompt_session()

    while True:
        try:
            if session:
                line = session.prompt([("class:prompt", "ReadLoop> ")])
            else:
                line = input("ReadLoop> ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/]")
            break

        if not _parse_and_run(line):
            console.print("[dim]Bye![/]")
            break

        console.print()


def main():
    """CLI entry point for `readloop` command and `python -m readloop`."""
    import sys
    if len(sys.argv) > 1:
        from readloop._run import main as run_main
        run_main()
    else:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        run_interactive()
