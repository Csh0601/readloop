"""ReadLoop Interactive CLI -- 类似 Claude Code 的交互式研究工具

Usage:
    python run.py          # 启动交互模式
    python run.py --help   # 查看脚本模式参数
"""
from __future__ import annotations

import webbrowser
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .config import (
    GRAPH_DIR, MEMORY_DIR, OUTPUT_DIR,
    REFERENCE_DIRS, DEEPSEEK_MODEL, CLAUDE_MODEL,
)

console = Console(force_terminal=True)


def _safe_output_path(user_input: str, base: Path) -> Path:
    """Resolve user-supplied path and ensure it stays within base directory."""
    resolved = (base / user_input).resolve()
    base_resolved = base.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise ValueError(f"Path escapes allowed directory: {resolved}")
    return resolved


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

VERSION = "2.1.0"

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
    "/clear":      {"args": "",              "desc": "Clear screen"},
    "/quit":       {"args": "",              "desc": "Exit ReadLoop"},
}

COMMAND_NAMES = list(COMMANDS.keys())


# ──────────────────────────────────────────────
# Welcome / Help
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


# ──────────────────────────────────────────────
# Status
# ──────────────────────────────────────────────

def _show_status():
    tree = Tree("[bold cyan]ReadLoop Status", guide_style="dim")

    # Papers
    papers_branch = tree.add("[bold]Papers")
    for ref_dir in REFERENCE_DIRS:
        if ref_dir.exists():
            count = sum(1 for x in ref_dir.iterdir() if x.is_dir() or x.suffix == ".pdf")
            papers_branch.add(f"{ref_dir.name}: {count} items")
        else:
            papers_branch.add(f"{ref_dir.name}: [red]not found[/]")

    # Analyses
    analysis_branch = tree.add("[bold]Analyses")
    if OUTPUT_DIR.exists():
        analyzed = [d for d in OUTPUT_DIR.iterdir()
                    if d.is_dir() and not d.name.startswith("00_") and (d / "analysis.md").exists()]
        analysis_branch.add(f"{len(analyzed)} papers analyzed")
        cross = OUTPUT_DIR / "00_cross_analysis" / "cross_analysis.md"
        analysis_branch.add(f"Cross-analysis: {'[green]yes[/]' if cross.exists() else '[dim]no[/]'}")
    else:
        analysis_branch.add("[dim]No output directory[/]")

    # Graph
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

    # Memory
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

    # Models
    model_branch = tree.add("[bold]LLM Config")
    model_branch.add(f"Primary: {DEEPSEEK_MODEL}")
    model_branch.add(f"Fallback: {CLAUDE_MODEL}")

    console.print(tree)


# ──────────────────────────────────────────────
# Lazy client (avoid loading on startup)
# ──────────────────────────────────────────────

from functools import lru_cache

@lru_cache(maxsize=1)
def _get_client():
    from .client import LLMClient
    return LLMClient()


# ──────────────────────────────────────────────
# Command Handlers
# ──────────────────────────────────────────────

def _cmd_list(args: str):
    from .reader import get_paper_name

    source = args.strip() if args.strip() in ("ref", "agent") else None
    ref_dir = REFERENCE_DIRS[0]
    agent_dir = REFERENCE_DIRS[1]

    papers = []
    if source != "agent" and ref_dir.exists():
        for d in sorted(ref_dir.iterdir()):
            if d.is_dir():
                papers.append(("ref", d.name, d))
    if source != "ref" and agent_dir.exists():
        for cat_dir in sorted(agent_dir.iterdir()):
            if cat_dir.is_dir():
                for pdf in sorted(cat_dir.glob("*.pdf")):
                    papers.append(("agent", pdf.stem, pdf))

    table = Table(title=f"Papers ({len(papers)})", border_style="dim")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Src", style="magenta", width=5)
    table.add_column("Name", style="white")
    for i, (src, name, _) in enumerate(papers, 1):
        table.add_row(str(i), src, name[:70])
    console.print(table)


def _cmd_analyze(args: str):
    keyword = args.strip()
    if not keyword:
        console.print("[red]Usage: /analyze <keyword>[/]")
        return

    # Find paper
    ref_dir = REFERENCE_DIRS[0]
    agent_dir = REFERENCE_DIRS[1]
    found = None
    for d in sorted(ref_dir.iterdir()) if ref_dir.exists() else []:
        if d.is_dir() and keyword.lower() in d.name.lower():
            found = d
            break
    if not found and agent_dir.exists():
        for cat_dir in sorted(agent_dir.iterdir()):
            if cat_dir.is_dir():
                for pdf in cat_dir.glob("*.pdf"):
                    if keyword.lower() in pdf.stem.lower():
                        found = pdf
                        break
            if found:
                break

    if not found:
        console.print(f"[red]Paper not found: '{keyword}'[/]")
        return

    console.print(f"[bold]Analyzing: {found.name}[/]")
    from .pipeline import analyze_single_paper
    client = _get_client()
    result = analyze_single_paper(found, client)
    if result.get("analysis"):
        lines = result["analysis"].count("\n") + 1
        console.print(f"[green]Done ({lines} lines) -> {result.get('output_path', '')}[/]")
    else:
        console.print("[red]Analysis failed[/]")


def _cmd_batch(args: str):
    parts = args.strip().split()
    source = parts[0] if parts and parts[0] in ("ref", "agent") else None
    cat = parts[1] if len(parts) > 1 and parts[1] in ("A", "B", "C") else None

    ref_dir = REFERENCE_DIRS[0]
    agent_dir = REFERENCE_DIRS[1]
    paths = []
    if source != "agent" and ref_dir.exists():
        paths.extend(sorted(d for d in ref_dir.iterdir() if d.is_dir()))
    if source != "ref" and agent_dir.exists():
        for cat_dir in sorted(agent_dir.iterdir()):
            if cat_dir.is_dir() and (not cat or cat_dir.name.startswith(cat)):
                paths.extend(sorted(cat_dir.glob("*.pdf")))

    if not paths:
        console.print("[red]No papers found[/]")
        return

    console.print(f"[bold]Batch analyzing {len(paths)} papers...[/]")
    from .pipeline import analyze_all_papers, generate_cross_analysis
    client = _get_client()
    results = analyze_all_papers(paths, client)
    successful = [r for r in results if r.get("analysis")]
    console.print(f"[green]Analyzed: {len(successful)}/{len(paths)}[/]")

    if len(successful) >= 2:
        console.print("[bold]Running cross-paper analysis...[/]")
        generate_cross_analysis(successful, client)
        console.print("[green]Cross-analysis saved[/]")


def _cmd_cross(_args: str):
    if not OUTPUT_DIR.exists():
        console.print("[red]No analyses found. Run /analyze or /batch first.[/]")
        return

    results = []
    for d in sorted(OUTPUT_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("00_") and (d / "analysis.md").exists():
            analysis = (d / "analysis.md").read_text(encoding="utf-8")
            results.append({"name": d.name, "analysis": analysis})

    if len(results) < 2:
        console.print(f"[red]Need 2+ analyses, found {len(results)}[/]")
        return

    console.print(f"[bold]Cross-analyzing {len(results)} papers...[/]")
    from .pipeline import generate_cross_analysis
    generate_cross_analysis(results, _get_client())
    console.print("[green]Cross-analysis saved[/]")


def _cmd_build(_args: str):
    console.print("[bold]Building knowledge graph...[/]")
    client = _get_client()
    from .knowledge.graph import build_graph_from_analyses
    from .knowledge.visualize import generate_overview
    graph = build_graph_from_analyses(OUTPUT_DIR, client)
    stats = graph.stats()
    console.print(f"  {stats['total_nodes']} nodes, {stats['total_edges']} edges")

    # Always save first
    graph.save(GRAPH_DIR / "graph.json")

    if stats["total_nodes"] >= 10:
        from .knowledge.cluster import cluster_graph, label_communities
        console.print("  Running community detection...")
        communities = cluster_graph(graph)
        labels = label_communities(graph, communities)
        graph.community_labels = labels
        graph.save(GRAPH_DIR / "graph.json")  # re-save with communities
        console.print(f"  {len(communities)} communities detected")

    overview = generate_overview(graph)
    (GRAPH_DIR / "overview.md").write_text(overview, encoding="utf-8")
    console.print("[green]Graph built and saved[/]")


def _cmd_graph(_args: str):
    from .knowledge.models import KnowledgeGraph
    graph_path = GRAPH_DIR / "graph.json"
    if not graph_path.exists():
        console.print("[red]No graph. Run /build first.[/]")
        return

    graph = KnowledgeGraph.load(graph_path)
    stats = graph.stats()
    communities = graph.get_communities()

    table = Table(title="Knowledge Graph", border_style="dim")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="cyan", justify="right")
    table.add_row("Nodes", str(stats["total_nodes"]))
    table.add_row("Edges", str(stats["total_edges"]))
    table.add_row("Communities", str(len(communities)))
    table.add_row("", "")
    for t, c in stats["node_types"].items():
        table.add_row(f"  {t}", str(c))
    table.add_row("", "")
    for r, c in sorted(stats["edge_relations"].items(), key=lambda x: -x[1]):
        table.add_row(f"  {r}", str(c))
    console.print(table)


def _cmd_cluster(_args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.cluster import cluster_graph, label_communities

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return

    console.print("[bold]Clustering...[/]")
    communities = cluster_graph(graph)
    labels = label_communities(graph, communities)
    graph.community_labels = labels
    graph.save(GRAPH_DIR / "graph.json")

    # Show only meaningful communities (>1 node)
    big = {cid: nodes for cid, nodes in communities.items() if len(nodes) > 1}
    table = Table(title=f"Communities ({len(big)} major / {len(communities)} total)", border_style="dim")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Label", style="white")
    table.add_column("Nodes", style="green", justify="right", width=6)
    table.add_column("Cohesion", style="yellow", justify="right", width=8)
    for cid in sorted(big.keys()):
        table.add_row(
            str(cid), labels.get(cid, "?"),
            str(len(big[cid])),
            f"{graph.community_cohesion.get(cid, 0):.2f}",
        )
    console.print(table)
    console.print(f"[dim]+ {len(communities) - len(big)} single-node isolates[/]")


def _cmd_viz(_args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.html_viz import generate_html

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return
    output = GRAPH_DIR / "graph.html"
    communities = graph.get_communities() or None
    generate_html(graph, output, communities=communities)
    webbrowser.open(str(output))
    console.print(f"[green]Opened: {output}[/]")


def _cmd_gods(args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.analyze import god_nodes

    n = int(args.strip()) if args.strip().isdigit() else 10
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    gods = god_nodes(graph, top_n=n)

    table = Table(title=f"God Nodes (Top {n})", border_style="dim")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Node", style="white")
    table.add_column("Type", style="magenta", width=8)
    table.add_column("Edges", style="green", justify="right", width=6)
    for i, g in enumerate(gods, 1):
        table.add_row(str(i), g["label"][:55], g["type"], str(g["edges"]))
    console.print(table)


def _cmd_surprises(args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.analyze import surprising_connections

    n = int(args.strip()) if args.strip().isdigit() else 5
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return

    surprises = surprising_connections(graph, communities, top_n=n)
    for s in surprises:
        console.print(f"  [bold]{s['source']}[/] --[yellow]{s['relation']}[/]--> [bold]{s['target']}[/]")
        console.print(f"  [dim]{s['why']}[/]\n")


def _cmd_questions(args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.analyze import suggest_questions

    n = int(args.strip()) if args.strip().isdigit() else 7
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return

    questions = suggest_questions(graph, communities, top_n=n)
    for q in questions:
        if q.get("question"):
            console.print(f"  [cyan][{q['type']}][/] {q['question']}")
            console.print(f"  [dim]{q['why']}[/]\n")

    report_lines = ["# Research Questions\n"]
    for q in questions:
        if q.get("question"):
            report_lines.append(f"### [{q['type']}] {q['question']}\n_{q['why']}_\n")
    path = GRAPH_DIR / "questions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"[green]Saved: {path}[/]")


def _cmd_gaps(_args: str):
    from .knowledge.models import KnowledgeGraph
    from .knowledge.graph import find_gaps

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return

    console.print("[bold]Analyzing research gaps (LLM)...[/]")
    gaps = find_gaps(graph, _get_client())
    path = GRAPH_DIR / "gaps.md"
    path.write_text(gaps, encoding="utf-8")
    console.print(Markdown(gaps[:2000]))
    if len(gaps) > 2000:
        console.print(f"[dim]... truncated. Full report: {path}[/]")
    console.print(f"\n[green]Saved: {path}[/]")


def _cmd_memory(_args: str):
    from .memory.models import MemoryStore
    from .memory.embeddings import EmbeddingIndex

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


def _cmd_build_mem(_args: str):
    console.print("[bold]Building memory store...[/]")
    from .memory.store import build_memory_from_analyses
    store, index = build_memory_from_analyses(OUTPUT_DIR, _get_client())
    stats = store.stats()
    console.print(f"[green]Memory: {stats['total_entries']} entries, {len(index)} embeddings[/]")


def _cmd_ask(args: str):
    query = args.strip()
    if not query:
        console.print("[red]Usage: /ask <your question>[/]")
        return

    console.print(f"[bold cyan]Q:[/] {query}\n")
    from .memory.search import ask_with_memory
    answer = ask_with_memory(query, _get_client())
    console.print(Markdown(answer))


def _cmd_review(args: str):
    topic = args.strip()
    if not topic:
        console.print("[red]Usage: /review <topic>[/]")
        return

    console.print(f"[bold]Generating review: {topic}[/]")
    from .features.review import generate_review
    path = generate_review(topic, _get_client())
    content = path.read_text(encoding="utf-8")
    console.print(Markdown(content[:3000]))
    if len(content) > 3000:
        console.print(f"[dim]... truncated[/]")
    console.print(f"\n[green]Saved: {path}[/]")


def _cmd_track(args: str):
    concept = args.strip()
    if not concept:
        console.print("[red]Usage: /track <concept name>[/]")
        return

    console.print(f"[bold]Tracking: {concept}[/]")
    from .features.evolution import track_concept
    try:
        path = track_concept(concept, _get_client())
        content = path.read_text(encoding="utf-8")
        console.print(Markdown(content[:2000]))
        console.print(f"\n[green]Saved: {path}[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")


def _cmd_propose(args: str):
    topic = args.strip() or None
    console.print("[bold]Generating research proposals...[/]")
    from .features.proposals import generate_proposals
    path = generate_proposals(_get_client(), topic)
    content = path.read_text(encoding="utf-8")
    console.print(Markdown(content[:3000]))
    if len(content) > 3000:
        console.print(f"[dim]... truncated[/]")
    console.print(f"\n[green]Saved: {path}[/]")


def _cmd_wiki(args: str):
    output_dir = args.strip()
    if not output_dir:
        out_path = OUTPUT_DIR / "wiki"
    else:
        out_path = _safe_output_path(output_dir, OUTPUT_DIR)

    from .knowledge.models import KnowledgeGraph
    from .knowledge.wiki_export import to_wiki

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return
    count = to_wiki(graph, communities, out_path)
    console.print(f"[green]Exported {count} wiki articles -> {out_path}[/]")


def _cmd_graphml(args: str):
    output_file = args.strip()
    if not output_file:
        out_path = GRAPH_DIR / "graph.graphml"
    else:
        out_path = _safe_output_path(output_file, OUTPUT_DIR)

    from .knowledge.models import KnowledgeGraph
    from .knowledge.graphml_export import to_graphml

    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    to_graphml(graph, out_path)
    console.print(f"[green]Saved: {out_path}[/]")


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

    # Split command and args
    parts = line.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Fuzzy match
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
        style = Style.from_dict({
            "prompt": "ansicyan bold",
        })
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

        console.print()  # blank line between commands
