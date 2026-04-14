"""Knowledge graph commands."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from ..client import LLMClient
from ..config import GRAPH_DIR, OUTPUT_DIR


def _load_graph():
    """Load graph, or return None if not found."""
    from ..knowledge.models import KnowledgeGraph

    path = GRAPH_DIR / "graph.json"
    if not path.exists():
        return None
    return KnowledgeGraph.load(path)


def cmd_build_graph(console: Console, client: LLMClient) -> None:
    """Build knowledge graph from all analyses, auto-cluster if large enough."""
    from ..knowledge.graph import build_graph_from_analyses
    from ..knowledge.visualize import generate_overview

    console.print("[bold]Building knowledge graph...[/]")
    graph = build_graph_from_analyses(OUTPUT_DIR, client)
    stats = graph.stats()
    console.print(f"  {stats['total_nodes']} nodes, {stats['total_edges']} edges")

    graph.save(GRAPH_DIR / "graph.json")

    if stats["total_nodes"] >= 10:
        from ..knowledge.cluster import cluster_graph, label_communities

        console.print("  Running community detection...")
        communities = cluster_graph(graph)
        labels = label_communities(graph, communities)
        graph.community_labels = labels
        graph.save(GRAPH_DIR / "graph.json")
        console.print(f"  {len(communities)} communities detected")

    overview = generate_overview(graph)
    (GRAPH_DIR / "overview.md").write_text(overview, encoding="utf-8")
    console.print("[green]Graph built and saved[/]")


def cmd_show_graph(console: Console) -> None:
    """Display graph statistics."""
    graph = _load_graph()
    if graph is None:
        console.print("[red]No graph. Run /build first.[/]")
        return

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


def cmd_viz_graph(console: Console) -> None:
    """Generate and open interactive graph visualization in browser."""
    import webbrowser

    from ..knowledge.html_viz import generate_html

    graph = _load_graph()
    if graph is None or graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return

    output = GRAPH_DIR / "graph.html"
    communities = graph.get_communities() or None
    generate_html(graph, output, communities=communities)
    webbrowser.open(str(output))
    console.print(f"[green]Opened: {output}[/]")


def cmd_cluster(console: Console) -> None:
    """Run community detection on the knowledge graph."""
    from ..knowledge.cluster import cluster_graph, label_communities

    graph = _load_graph()
    if graph is None or graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return

    console.print("[bold]Clustering...[/]")
    communities = cluster_graph(graph)
    labels = label_communities(graph, communities)
    graph.community_labels = labels
    graph.save(GRAPH_DIR / "graph.json")

    big = {cid: nodes for cid, nodes in communities.items() if len(nodes) > 1}
    table = Table(
        title=f"Communities ({len(big)} major / {len(communities)} total)",
        border_style="dim",
    )
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Label", style="white")
    table.add_column("Nodes", style="green", justify="right", width=6)
    table.add_column("Cohesion", style="yellow", justify="right", width=8)
    for cid in sorted(big.keys()):
        table.add_row(
            str(cid),
            labels.get(cid, "?"),
            str(len(big[cid])),
            f"{graph.community_cohesion.get(cid, 0):.2f}",
        )
    console.print(table)
    console.print(f"[dim]+ {len(communities) - len(big)} single-node isolates[/]")


def cmd_gaps(console: Console, client: LLMClient) -> None:
    """Find research gaps using LLM analysis of the graph."""
    from ..knowledge.graph import find_gaps

    graph = _load_graph()
    if graph is None or graph.stats()["total_nodes"] == 0:
        console.print("[red]Graph empty. Run /build first.[/]")
        return

    console.print("[bold]Analyzing research gaps (LLM)...[/]")
    gaps = find_gaps(graph, client)
    path = GRAPH_DIR / "gaps.md"
    path.write_text(gaps, encoding="utf-8")
    console.print(Markdown(gaps[:2000]))
    if len(gaps) > 2000:
        console.print(f"[dim]... truncated. Full report: {path}[/]")
    console.print(f"\n[green]Saved: {path}[/]")


def cmd_gods(console: Console, top_n: int = 10) -> None:
    """Display the most connected nodes in the graph."""
    from ..knowledge.analyze import god_nodes

    graph = _load_graph()
    if graph is None:
        console.print("[red]No graph. Run /build first.[/]")
        return

    gods = god_nodes(graph, top_n=top_n)
    table = Table(title=f"God Nodes (Top {top_n})", border_style="dim")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Node", style="white")
    table.add_column("Type", style="magenta", width=8)
    table.add_column("Edges", style="green", justify="right", width=6)
    for i, g in enumerate(gods, 1):
        table.add_row(str(i), g["label"][:55], g["type"], str(g["edges"]))
    console.print(table)


def cmd_surprises(console: Console, top_n: int = 5) -> None:
    """Display cross-community surprising connections."""
    from ..knowledge.analyze import surprising_connections

    graph = _load_graph()
    if graph is None:
        console.print("[red]No graph. Run /build first.[/]")
        return

    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return

    surprises = surprising_connections(graph, communities, top_n=top_n)
    for s in surprises:
        console.print(
            f"  [bold]{s['source']}[/] --[yellow]{s['relation']}[/]--> [bold]{s['target']}[/]"
        )
        console.print(f"  [dim]{s['why']}[/]\n")


def cmd_analyze_graph(console: Console) -> None:
    """Combined god nodes + surprising connections + save report."""
    from ..knowledge.analyze import god_nodes, surprising_connections

    graph = _load_graph()
    if graph is None:
        console.print("[red]No graph. Run /build first.[/]")
        return

    communities = graph.get_communities()
    gods = god_nodes(graph, top_n=10)

    console.print("\n[bold]God Nodes (most connected):[/]")
    for i, g in enumerate(gods, 1):
        console.print(f"  {i}. {g['label']} ({g['type']}) -- {g['edges']} edges")

    surprises: list[dict] = []
    if communities:
        console.print("\n[bold]Surprising Connections:[/]")
        surprises = surprising_connections(graph, communities, top_n=5)
        for s in surprises:
            console.print(f"  - {s['source']} --{s['relation']}--> {s['target']}")
            console.print(f"    [dim]{s['why']}[/dim]")
    else:
        console.print("[yellow]No communities. Run --cluster first.[/]")

    report_lines = ["# Graph Analysis\n", "## God Nodes\n"]
    for i, g in enumerate(gods, 1):
        report_lines.append(f"{i}. **{g['label']}** ({g['type']}) -- {g['edges']} edges")
    report_lines.append("\n## Surprising Connections\n")
    for s in surprises:
        report_lines.append(f"- **{s['source']}** --{s['relation']}--> **{s['target']}**")
        report_lines.append(f"  - Why: {s['why']}")
    report_path = GRAPH_DIR / "analysis.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"\n[green]Saved: {report_path}[/]")


def cmd_questions(console: Console, top_n: int = 7) -> None:
    """Generate research questions from graph communities."""
    from ..knowledge.analyze import suggest_questions

    graph = _load_graph()
    if graph is None:
        console.print("[red]No graph. Run /build first.[/]")
        return

    communities = graph.get_communities()
    if not communities:
        console.print("[yellow]No communities. Run /cluster first.[/]")
        return

    console.print("[bold]Generating research questions...[/]")
    questions = suggest_questions(graph, communities, top_n=top_n)
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
