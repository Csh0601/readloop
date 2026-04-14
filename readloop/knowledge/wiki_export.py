"""Obsidian-compatible wiki export for ReadLoop knowledge graphs.

Generates index.md, per-community articles, per-paper pages, and
per-concept pages with [[wikilinks]] for cross-referencing.

Adapted from graphify/wiki.py for academic paper domain.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import KnowledgeGraph, Node


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename. Prevents path traversal."""
    cleaned = re.sub(r'[\\/*?:"<>|#^[\]]', "", name.replace("\n", " ")).strip()
    cleaned = Path(cleaned).name  # strip any remaining directory components
    cleaned = cleaned.replace("..", "").strip(".").strip()
    return cleaned[:80] or "unnamed"


def _wikilink(label: str) -> str:
    return f"[[{_safe_filename(label)}]]"


def to_wiki(
    graph: KnowledgeGraph,
    communities: dict[int, list[str]],
    output_dir: Path,
) -> int:
    """Generate an Obsidian vault from the knowledge graph.

    Returns number of articles written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    # Community articles
    for cid, node_ids in communities.items():
        label = graph.community_labels.get(cid, f"Community {cid}")
        article = _community_article(graph, cid, node_ids, label)
        (output_dir / f"{_safe_filename(label)}.md").write_text(article, encoding="utf-8")
        count += 1

    # Per-node articles (papers always, high-degree concepts/methods)
    for node in graph.nodes.values():
        edge_count = len(graph.get_edges_for_node(node.id))
        if node.type == "paper" or edge_count >= 3:
            article = _node_article(graph, node)
            (output_dir / f"{_safe_filename(node.label)}.md").write_text(article, encoding="utf-8")
            count += 1

    # Index
    (output_dir / "index.md").write_text(
        _index_md(graph, communities),
        encoding="utf-8",
    )
    count += 1

    return count


def _community_article(
    graph: KnowledgeGraph,
    cid: int,
    node_ids: list[str],
    label: str,
) -> str:
    """Generate a research theme overview article."""
    nodes = [graph.get_node(nid) for nid in node_ids if graph.get_node(nid)]
    papers = [n for n in nodes if n.type == "paper"]
    concepts = [n for n in nodes if n.type == "concept"]
    methods = [n for n in nodes if n.type == "method"]
    datasets = [n for n in nodes if n.type == "dataset"]

    cohesion = graph.community_cohesion.get(cid, 0)

    lines = [
        f"# {label}",
        "",
        f"**Community {cid}** | {len(nodes)} nodes | Cohesion: {cohesion:.2f}",
        "",
    ]

    if papers:
        lines.append("## Papers")
        lines.append("")
        for p in sorted(papers, key=lambda x: x.label):
            year = p.metadata.get("year", "")
            lines.append(f"- {_wikilink(p.label)} ({year})")
        lines.append("")

    if concepts:
        lines.append("## Key Concepts")
        lines.append("")
        for c in sorted(concepts, key=lambda x: x.label):
            defn = c.metadata.get("definition", "")[:100]
            lines.append(f"- {_wikilink(c.label)}: {defn}")
        lines.append("")

    if methods:
        lines.append("## Methods")
        lines.append("")
        for m in sorted(methods, key=lambda x: x.label):
            desc = m.metadata.get("description", "")[:100]
            lines.append(f"- {_wikilink(m.label)}: {desc}")
        lines.append("")

    if datasets:
        lines.append("## Datasets")
        lines.append("")
        for d in sorted(datasets, key=lambda x: x.label):
            lines.append(f"- {_wikilink(d.label)}")
        lines.append("")

    # Cross-community connections
    cross = []
    for nid in node_ids:
        for edge in graph.get_edges_for_node(nid):
            other = edge.target if edge.source == nid else edge.source
            other_node = graph.get_node(other)
            if other_node and other_node.community is not None and other_node.community != cid:
                other_comm = graph.community_labels.get(
                    other_node.community, f"Community {other_node.community}"
                )
                cross.append(f"- {_wikilink(other_node.label)} ({edge.relation}) -> {_wikilink(other_comm)}")

    if cross:
        lines.append("## Cross-Theme Connections")
        lines.append("")
        seen = set()
        for c in cross:
            if c not in seen:
                lines.append(c)
                seen.add(c)
            if len(seen) >= 15:
                break
        lines.append("")

    return "\n".join(lines)


def _node_article(graph: KnowledgeGraph, node: Node) -> str:
    """Generate a per-node detail article."""
    lines = [f"# {node.label}", ""]

    lines.append(f"**Type:** {node.type}")
    if node.community is not None:
        comm_label = graph.community_labels.get(node.community, f"Community {node.community}")
        lines.append(f"**Community:** {_wikilink(comm_label)}")
    lines.append("")

    # Metadata
    if node.type == "paper":
        year = node.metadata.get("year", "")
        venue = node.metadata.get("venue", "")
        tags = ", ".join(node.metadata.get("domain_tags", []))
        if year:
            lines.append(f"**Year:** {year}")
        if venue:
            lines.append(f"**Venue:** {venue}")
        if tags:
            lines.append(f"**Tags:** {tags}")
    elif node.type == "concept":
        defn = node.metadata.get("definition", "")
        if defn:
            lines.append(f"**Definition:** {defn}")
    elif node.type == "method":
        desc = node.metadata.get("description", "")
        if desc:
            lines.append(f"**Description:** {desc}")
    lines.append("")

    # Connections
    edges = graph.get_edges_for_node(node.id)
    if edges:
        lines.append("## Connections")
        lines.append("")
        for edge in edges:
            other_id = edge.target if edge.source == node.id else edge.source
            other = graph.get_node(other_id)
            other_label = other.label if other else other_id
            direction = "->" if edge.source == node.id else "<-"
            evidence = f" -- {edge.evidence[:80]}" if edge.evidence else ""
            lines.append(f"- {direction} **{edge.relation}** {_wikilink(other_label)}{evidence}")
        lines.append("")

    return "\n".join(lines)


def _index_md(graph: KnowledgeGraph, communities: dict[int, list[str]]) -> str:
    """Generate the vault index page."""
    stats = graph.stats()
    lines = [
        "# ReadLoop Knowledge Graph",
        "",
        f"**{stats['total_nodes']} nodes** | **{stats['total_edges']} edges** | "
        f"**{len(communities)} communities**",
        "",
        "## Research Themes",
        "",
    ]

    for cid in sorted(communities.keys()):
        label = graph.community_labels.get(cid, f"Community {cid}")
        size = len(communities[cid])
        cohesion = graph.community_cohesion.get(cid, 0)
        lines.append(f"- {_wikilink(label)} ({size} nodes, cohesion {cohesion:.2f})")
    lines.append("")

    # Top connected nodes
    from .analyze import god_nodes
    gods = god_nodes(graph, top_n=10)
    if gods:
        lines.append("## Core Concepts")
        lines.append("")
        for g in gods:
            lines.append(f"- {_wikilink(g['label'])} ({g['type']}, {g['edges']} edges)")
        lines.append("")

    # Node type summary
    lines.append("## By Type")
    lines.append("")
    for t, c in stats["node_types"].items():
        lines.append(f"- **{t}**: {c}")
    lines.append("")

    return "\n".join(lines)
