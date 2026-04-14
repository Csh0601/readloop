"""知识图谱 Mermaid 可视化"""
from __future__ import annotations

from .models import KnowledgeGraph


def generate_overview(graph: KnowledgeGraph) -> str:
    """Generate a Markdown overview with Mermaid diagrams and stats."""
    stats = graph.stats()
    papers = graph.find_nodes_by_type("paper")
    concepts = graph.find_nodes_by_type("concept")
    methods = graph.find_nodes_by_type("method")

    lines = [
        "# ReadLoop Knowledge Graph Overview",
        "",
        "## Statistics",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Nodes | {stats['total_nodes']} |",
        f"| Total Edges | {stats['total_edges']} |",
        f"| Papers | {stats['node_types'].get('paper', 0)} |",
        f"| Concepts | {stats['node_types'].get('concept', 0)} |",
        f"| Methods | {stats['node_types'].get('method', 0)} |",
        f"| Datasets | {stats['node_types'].get('dataset', 0)} |",
        "",
        "## Edge Types",
        "",
        "| Relation | Count |",
        "|----------|-------|",
    ]
    for rel, count in sorted(stats["edge_relations"].items(), key=lambda x: -x[1]):
        lines.append(f"| {rel} | {count} |")

    # Paper-concept graph
    lines.extend([
        "",
        "## Paper-Concept Network",
        "",
        "```mermaid",
        "graph LR",
    ])

    # Add paper nodes
    for p in papers:
        short = p.label[:30].replace('"', "'")
        safe_id = p.id.replace(":", "_").replace("-", "_")
        lines.append(f'    {safe_id}["{short}"]')

    # Add concept nodes (only those with 2+ paper connections)
    concept_connections = {}
    for e in graph.edges:
        if e.source.startswith("paper:") and e.target.startswith("concept:"):
            concept_connections.setdefault(e.target, []).append(e.source)

    popular_concepts = {
        k: v for k, v in concept_connections.items() if len(v) >= 2
    }

    for c_id in popular_concepts:
        node = graph.get_node(c_id)
        if node:
            short = node.label[:25].replace('"', "'")
            safe_id = c_id.replace(":", "_").replace("-", "_")
            lines.append(f'    {safe_id}("{short}"):::concept')

    # Add edges for popular concepts
    for c_id, paper_ids in popular_concepts.items():
        safe_c = c_id.replace(":", "_").replace("-", "_")
        for p_id in paper_ids:
            safe_p = p_id.replace(":", "_").replace("-", "_")
            lines.append(f"    {safe_p} --> {safe_c}")

    lines.extend([
        '    classDef concept fill:#f9f,stroke:#333',
        "```",
        "",
        "## Paper List",
        "",
    ])

    for i, p in enumerate(papers, 1):
        year = p.metadata.get("year", "?")
        tags = ", ".join(p.metadata.get("domain_tags", [])[:3])
        lines.append(f"{i}. **{p.label}** ({year}) [{tags}]")

    lines.extend([
        "",
        "## Most Connected Concepts",
        "",
    ])

    sorted_concepts = sorted(popular_concepts.items(), key=lambda x: -len(x[1]))
    for c_id, paper_ids in sorted_concepts[:15]:
        node = graph.get_node(c_id)
        label = node.label if node else c_id
        lines.append(f"- **{label}** ({len(paper_ids)} papers)")

    return "\n".join(lines)
