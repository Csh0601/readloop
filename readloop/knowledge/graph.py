"""知识图谱管理 -- 跨论文边检测 + 空白发现"""
from __future__ import annotations

from pathlib import Path

from ..client import LLMClient
from ..config import GRAPH_DIR
from .models import KnowledgeGraph, Node, Edge
from .prompts import FIND_GAPS


def build_graph_from_analyses(
    output_dir: Path,
    client: LLMClient,
) -> KnowledgeGraph:
    """Build full knowledge graph from all existing analysis + extraction files."""
    from .extractor import extract_from_analysis, extraction_to_graph
    import json

    graph_path = GRAPH_DIR / "graph.json"
    graph = KnowledgeGraph()

    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    console = Console(force_terminal=True)

    # Find all paper output dirs with analyses
    paper_dirs = [
        d for d in sorted(output_dir.iterdir())
        if d.is_dir() and not d.name.startswith("00_") and (d / "analysis.md").exists()
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Building knowledge graph", total=len(paper_dirs))
        for paper_dir in paper_dirs:
            progress.update(task, description=f"[cyan]{paper_dir.name[:50]}[/]")
            extraction_path = paper_dir / "extraction.json"

            if extraction_path.exists():
                extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
            else:
                analysis = (paper_dir / "analysis.md").read_text(encoding="utf-8")
                extraction = extract_from_analysis(analysis, paper_dir.name, client)
                extraction_path.write_text(
                    json.dumps(extraction, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            extraction_to_graph(extraction, paper_dir.name, graph)
            progress.advance(task)

    # Canonicalize synonymous concepts before cross-paper detection
    try:
        from .canonicalize import canonicalize_concepts, prune_hapax_nodes

        remap = canonicalize_concepts(graph)
        if remap:
            console.print(f"  [dim]merged {len(remap)} synonymous nodes[/]")

        pruned = prune_hapax_nodes(graph)
        if pruned:
            console.print(f"  [dim]pruned {pruned} single-occurrence nodes[/]")
    except Exception as e:
        console.print(f"  [yellow]canonicalization skipped: {e}[/]")

    # Detect cross-paper edges (more accurate after merge)
    detect_cross_paper_edges(graph)

    dropped = prune_dangling_edges(graph)
    if dropped:
        console.print(f"  [dim]dropped {dropped} dangling edges[/]")

    # Save
    graph.save(graph_path)
    return graph


def add_paper_to_graph(
    paper_dir: Path,
    client: LLMClient,
) -> KnowledgeGraph:
    """Incrementally add a single paper to the existing graph."""
    from .extractor import extract_from_analysis, extraction_to_graph
    import json

    graph_path = GRAPH_DIR / "graph.json"
    graph = KnowledgeGraph.load(graph_path)

    analysis_path = paper_dir / "analysis.md"
    extraction_path = paper_dir / "extraction.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No analysis.md in {paper_dir}")

    if extraction_path.exists():
        extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    else:
        analysis = analysis_path.read_text(encoding="utf-8")
        extraction = extract_from_analysis(analysis, paper_dir.name, client)
        extraction_path.write_text(
            json.dumps(extraction, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    extraction_to_graph(extraction, paper_dir.name, graph)
    detect_cross_paper_edges(graph)
    prune_dangling_edges(graph)
    graph.save(graph_path)
    return graph


def detect_cross_paper_edges(graph: KnowledgeGraph) -> int:
    """Detect shared concepts/methods across papers based on node ID overlap.

    Returns number of new edges added.
    """
    from collections import defaultdict

    # Group edges by target concept/method — if 2+ papers link to the same node,
    # those papers share that concept
    node_to_papers: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.source.startswith("paper:"):
            node_to_papers[edge.target].add(edge.source)

    added = 0
    existing_pairs = {
        (e.source, e.target, e.relation) for e in graph.edges
    }

    for node_id, papers in node_to_papers.items():
        if len(papers) < 2:
            continue
        papers_list = sorted(papers)
        for i in range(len(papers_list)):
            for j in range(i + 1, len(papers_list)):
                pair = (papers_list[i], papers_list[j], "shared_concept")
                if pair not in existing_pairs:
                    node = graph.get_node(node_id)
                    label = node.label if node else node_id
                    graph.add_edge(Edge(
                        source=papers_list[i],
                        target=papers_list[j],
                        relation="shared_concept",
                        weight=0.8,
                        evidence=f"Both reference: {label}",
                    ))
                    existing_pairs.add(pair)
                    added += 1
    return added


def prune_dangling_edges(graph: KnowledgeGraph) -> int:
    """Remove edges whose source/target nodes do not exist."""
    before = len(graph.edges)
    graph.edges = [
        edge for edge in graph.edges
        if edge.source in graph.nodes and edge.target in graph.nodes
    ]
    return before - len(graph.edges)


def find_gaps(graph: KnowledgeGraph, client: LLMClient) -> str:
    """Use LLM to analyze graph and find research gaps. Returns Markdown."""
    stats = graph.stats()
    concepts = [
        f"- {n.label}: {n.metadata.get('definition', '')}"
        for n in graph.find_nodes_by_type("concept")
    ]
    methods = [
        f"- {n.label}: {n.metadata.get('description', '')}"
        for n in graph.find_nodes_by_type("method")
    ]
    edges = [
        f"- [{e.source}] --{e.relation}--> [{e.target}] ({e.evidence})"
        for e in graph.edges[:200]  # limit for prompt size
    ]

    prompt = FIND_GAPS.format(
        graph_stats=str(stats),
        concepts="\n".join(concepts[:80]),
        methods="\n".join(methods[:40]),
        edges="\n".join(edges),
    )
    return client.chat(prompt, max_tokens=8000)
