"""ReadLoop v2 -- Agent Harness for Paper Research

Interactive mode (recommended):
    python run.py                                  # Launch interactive CLI

Script mode (for automation):
    python run.py --list                           # List available papers
    python run.py --single "A-MEM"                 # Analyze single paper
    python run.py --build-graph                    # Build knowledge graph
    python run.py --ask "query"                    # Semantic search + LLM answer
    python run.py --help                           # Show all script options
"""
import argparse
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from src.config import REFERENCE_DIRS, OUTPUT_DIR, GRAPH_DIR, MEMORY_DIR
from src.client import LLMClient
from src.pipeline import (
    analyze_single_paper,
    analyze_all_papers,
    generate_cross_analysis,
)
from src.reader import get_paper_name

from rich.console import Console
from rich.table import Table

console = Console(force_terminal=True)

REF_DIR = REFERENCE_DIRS[0]
AGENT_DIR = REFERENCE_DIRS[1]


# --- Paper collection (unchanged) ---

def collect_ref_papers() -> list[tuple[str, Path]]:
    results = []
    if not REF_DIR.exists():
        return results
    for d in sorted(REF_DIR.iterdir()):
        if d.is_dir():
            results.append(("ref", d))
    return results


def collect_agent_papers(category: str | None = None) -> list[tuple[str, Path]]:
    results = []
    if not AGENT_DIR.exists():
        return results
    for cat_dir in sorted(AGENT_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        if category and not cat_dir.name.startswith(category):
            continue
        for pdf in sorted(cat_dir.glob("*.pdf")):
            results.append(("agent", pdf))
    return results


def collect_all(source=None, category=None):
    if source == "ref":
        return collect_ref_papers()
    elif source == "agent":
        return collect_agent_papers(category)
    else:
        return collect_ref_papers() + collect_agent_papers(category)


def list_papers(source=None, category=None):
    papers = collect_all(source, category)
    table = Table(title=f"Papers ({len(papers)})")
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


def find_paper(keyword):
    for src, path in collect_all():
        name = path.stem if path.is_file() else path.name
        if keyword.lower() in name.lower():
            return src, path
    return None


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="ReadLoop v2")

    # Analysis
    parser.add_argument("--single", type=str, help="Analyze single paper (keyword)")
    parser.add_argument("--source", choices=["ref", "agent"])
    parser.add_argument("--cat", choices=["A", "B", "C"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--cross-only", action="store_true")
    parser.add_argument("--list", action="store_true")

    # Knowledge Graph
    parser.add_argument("--build-graph", action="store_true", help="Build knowledge graph")
    parser.add_argument("--show-graph", action="store_true", help="Show graph stats")
    parser.add_argument("--viz-graph", action="store_true", help="Open interactive graph visualization")
    parser.add_argument("--gaps", action="store_true", help="Find research gaps")
    parser.add_argument("--cluster", action="store_true", help="Run community detection")
    parser.add_argument("--analyze-graph", action="store_true", help="God nodes + surprising connections")
    parser.add_argument("--questions", action="store_true", help="Generate research questions from graph")

    # Export
    parser.add_argument("--export-wiki", type=str, metavar="DIR", help="Export Obsidian wiki")
    parser.add_argument("--export-graphml", type=str, metavar="FILE", help="Export GraphML")

    # Memory
    parser.add_argument("--build-memory", action="store_true", help="Build memory store")
    parser.add_argument("--ask", type=str, help="Query the knowledge base")
    parser.add_argument("--memory-stats", action="store_true")

    # Features
    parser.add_argument("--review", type=str, help="Generate literature review on topic")
    parser.add_argument("--track-concept", type=str, help="Track concept evolution")
    parser.add_argument("--propose", action="store_true", help="Generate research proposals")
    parser.add_argument("--topic", type=str, help="Topic for proposals")

    args = parser.parse_args()

    if args.list:
        list_papers(args.source, args.cat)
        return

    # --- Knowledge Graph commands ---
    if args.build_graph:
        _cmd_build_graph()
        return

    if args.show_graph:
        _cmd_show_graph()
        return

    if args.viz_graph:
        _cmd_viz_graph()
        return

    if args.gaps:
        _cmd_gaps()
        return

    if args.cluster:
        _cmd_cluster()
        return

    if args.analyze_graph:
        _cmd_analyze_graph()
        return

    if args.questions:
        _cmd_questions()
        return

    if args.export_wiki:
        _cmd_export_wiki(args.export_wiki)
        return

    if args.export_graphml:
        _cmd_export_graphml(args.export_graphml)
        return

    # --- Memory commands ---
    if args.build_memory:
        _cmd_build_memory()
        return

    if args.ask:
        _cmd_ask(args.ask)
        return

    if args.memory_stats:
        _cmd_memory_stats()
        return

    # --- Feature commands ---
    if args.review:
        _cmd_review(args.review)
        return

    if args.track_concept:
        _cmd_track_concept(args.track_concept)
        return

    if args.propose:
        _cmd_propose(args.topic)
        return

    # --- No script args: launch interactive mode ---
    if not any([
        args.single, args.source, args.all, args.cross_only,
    ]):
        from src.cli import run_interactive
        run_interactive()
        return

    # --- Analysis commands (script mode) ---
    console.print("[bold]ReadLoop v2[/]")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = LLMClient()

    if args.single:
        match = find_paper(args.single)
        if not match:
            console.print(f"[red]Not found: '{args.single}'[/]")
            list_papers()
            return
        _, path = match
        analyze_single_paper(path, client)

    elif args.cross_only:
        results = _load_existing_results()
        if results:
            generate_cross_analysis(results, client)
        else:
            console.print("[red]No analyses found. Run analysis first.[/]")

    else:
        papers = collect_all(args.source, args.cat)
        if not papers:
            console.print("[red]No papers found.[/]")
            return
        console.print(f"[bold]{len(papers)} papers[/]\n")
        paths = [p for _, p in papers]
        results = analyze_all_papers(paths, client)
        successful = [r for r in results if r.get("analysis")]
        if len(successful) >= 2:
            generate_cross_analysis(successful, client)
        console.print(f"\n[bold green]Done: {len(successful)}/{len(papers)}[/]")


# --- Command implementations ---

def _cmd_build_graph():
    console.print("[bold]Building knowledge graph...[/]")
    client = LLMClient()
    from src.knowledge.graph import build_graph_from_analyses
    from src.knowledge.visualize import generate_overview
    graph = build_graph_from_analyses(OUTPUT_DIR, client)
    stats = graph.stats()
    console.print(f"[green]Graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges[/]")

    # Always save first
    graph.save(GRAPH_DIR / "graph.json")

    # Auto-cluster if graph has enough nodes
    if stats["total_nodes"] >= 10:
        from src.knowledge.cluster import cluster_graph, label_communities
        console.print("[bold]Running community detection...[/]")
        communities = cluster_graph(graph)
        labels = label_communities(graph, communities)
        graph.community_labels = labels
        graph.save(GRAPH_DIR / "graph.json")  # re-save with communities
        console.print(f"[green]Detected {len(communities)} communities[/]")

    # Generate overview
    overview = generate_overview(graph)
    overview_path = GRAPH_DIR / "overview.md"
    overview_path.write_text(overview, encoding="utf-8")
    console.print(f"[green]Saved: {overview_path}[/]")


def _cmd_show_graph():
    from src.knowledge.models import KnowledgeGraph
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    stats = graph.stats()
    table = Table(title="Knowledge Graph")
    table.add_column("Metric")
    table.add_column("Value", style="cyan")
    table.add_row("Nodes", str(stats["total_nodes"]))
    table.add_row("Edges", str(stats["total_edges"]))
    for t, c in stats["node_types"].items():
        table.add_row(f"  {t}", str(c))
    for r, c in stats["edge_relations"].items():
        table.add_row(f"  edge:{r}", str(c))
    console.print(table)


def _cmd_viz_graph():
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.html_viz import generate_html
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run --build-graph first.[/]")
        return
    output_path = GRAPH_DIR / "graph.html"
    communities = graph.get_communities() or None
    generate_html(graph, output_path, communities=communities)
    console.print(f"[green]Saved: {output_path}[/]")
    import webbrowser
    webbrowser.open(str(output_path))


def _cmd_gaps():
    console.print("[bold]Analyzing research gaps...[/]")
    client = LLMClient()
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.graph import find_gaps
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run --build-graph first.[/]")
        return
    gaps = find_gaps(graph, client)
    gaps_path = GRAPH_DIR / "gaps.md"
    gaps_path.write_text(gaps, encoding="utf-8")
    console.print(f"[green]Saved: {gaps_path}[/]")
    console.print(gaps[:500] + "...")


def _cmd_build_memory():
    console.print("[bold]Building memory store...[/]")
    client = LLMClient()
    from src.memory.store import build_memory_from_analyses
    store, index = build_memory_from_analyses(OUTPUT_DIR, client)
    stats = store.stats()
    console.print(f"[green]Memory: {stats['total_entries']} entries, {stats['papers_covered']} papers[/]")
    console.print(f"[green]Embeddings: {len(index)} vectors[/]")


def _cmd_ask(query: str):
    client = LLMClient()
    from src.memory.search import ask_with_memory
    console.print(f"[bold]Q: {query}[/]\n")
    answer = ask_with_memory(query, client)
    console.print(answer)


def _cmd_memory_stats():
    from src.memory.models import MemoryStore
    from src.memory.embeddings import EmbeddingIndex
    store = MemoryStore.load(MEMORY_DIR / "memory_store.json")
    index = EmbeddingIndex.load(MEMORY_DIR)
    stats = store.stats()
    table = Table(title="Memory Store")
    table.add_column("Metric")
    table.add_column("Value", style="cyan")
    table.add_row("Total entries", str(stats["total_entries"]))
    table.add_row("Papers covered", str(stats["papers_covered"]))
    table.add_row("Embedding vectors", str(len(index)))
    for t, c in stats["type_counts"].items():
        table.add_row(f"  {t}", str(c))
    console.print(table)


def _cmd_review(topic: str):
    console.print(f"[bold]Generating review: {topic}[/]")
    client = LLMClient()
    from src.features.review import generate_review
    path = generate_review(topic, client)
    console.print(f"[green]Saved: {path}[/]")


def _cmd_track_concept(concept: str):
    console.print(f"[bold]Tracking concept: {concept}[/]")
    client = LLMClient()
    from src.features.evolution import track_concept
    path = track_concept(concept, client)
    console.print(f"[green]Saved: {path}[/]")


def _cmd_propose(topic: str | None = None):
    console.print("[bold]Generating research proposals...[/]")
    client = LLMClient()
    from src.features.proposals import generate_proposals
    path = generate_proposals(client, topic)
    console.print(f"[green]Saved: {path}[/]")


def _cmd_cluster():
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.cluster import cluster_graph, label_communities
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    if graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run --build-graph first.[/]")
        return
    console.print("[bold]Running community detection...[/]")
    communities = cluster_graph(graph)
    labels = label_communities(graph, communities)
    graph.community_labels = labels
    graph.save(GRAPH_DIR / "graph.json")

    table = Table(title=f"Communities ({len(communities)})")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Label", style="white")
    table.add_column("Nodes", style="green", width=6)
    table.add_column("Cohesion", style="yellow", width=8)
    for cid in sorted(communities.keys()):
        table.add_row(
            str(cid),
            labels.get(cid, "?"),
            str(len(communities[cid])),
            f"{graph.community_cohesion.get(cid, 0):.2f}",
        )
    console.print(table)


def _cmd_analyze_graph():
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.analyze import god_nodes, surprising_connections
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()

    console.print("\n[bold]God Nodes (most connected):[/]")
    gods = god_nodes(graph, top_n=10)
    for i, g in enumerate(gods, 1):
        console.print(f"  {i}. {g['label']} ({g['type']}) -- {g['edges']} edges")

    if communities:
        console.print("\n[bold]Surprising Connections:[/]")
        surprises = surprising_connections(graph, communities, top_n=5)
        for s in surprises:
            console.print(f"  - {s['source']} --{s['relation']}--> {s['target']}")
            console.print(f"    [dim]{s['why']}[/dim]")
    else:
        surprises = []
        console.print("[yellow]No communities. Run --cluster first for cross-community analysis.[/]")

    # Save report
    report_lines = ["# Graph Analysis\n"]
    report_lines.append("## God Nodes\n")
    for i, g in enumerate(gods, 1):
        report_lines.append(f"{i}. **{g['label']}** ({g['type']}) -- {g['edges']} edges")
    report_lines.append("\n## Surprising Connections\n")
    for s in surprises:
        report_lines.append(f"- **{s['source']}** --{s['relation']}--> **{s['target']}**")
        report_lines.append(f"  - Why: {s['why']}")
    report_path = GRAPH_DIR / "analysis.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"\n[green]Saved: {report_path}[/]")


def _cmd_questions():
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.analyze import suggest_questions
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run --cluster first.[/]")
        return

    console.print("[bold]Generating research questions...[/]")
    questions = suggest_questions(graph, communities, top_n=7)

    for q in questions:
        if q.get("question"):
            console.print(f"  [{q['type']}] {q['question']}")
            console.print(f"    [dim]{q['why']}[/dim]")

    report_lines = ["# Research Questions\n"]
    for q in questions:
        if q.get("question"):
            report_lines.append(f"### [{q['type']}] {q['question']}")
            report_lines.append(f"_{q['why']}_\n")
    report_path = GRAPH_DIR / "questions.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"\n[green]Saved: {report_path}[/]")


def _cmd_export_wiki(output_dir: str):
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.wiki_export import to_wiki
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run --cluster first.[/]")
        return
    count = to_wiki(graph, communities, Path(output_dir))
    console.print(f"[green]Exported {count} wiki articles to {output_dir}[/]")


def _cmd_export_graphml(output_file: str):
    from src.knowledge.models import KnowledgeGraph
    from src.knowledge.graphml_export import to_graphml
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    path = to_graphml(graph, Path(output_file))
    console.print(f"[green]Saved: {path}[/]")


def _load_existing_results():
    results = []
    if not OUTPUT_DIR.exists():
        return results
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("00_"):
            continue
        report = d / "analysis.md"
        if report.exists():
            analysis = report.read_text(encoding="utf-8")
            results.append({"name": d.name, "analysis": analysis})
    return results


if __name__ == "__main__":
    main()
