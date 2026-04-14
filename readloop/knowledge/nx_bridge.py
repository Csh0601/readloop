"""Bridge between ReadLoop KnowledgeGraph and NetworkX."""
from __future__ import annotations

import networkx as nx

from .models import KnowledgeGraph


def to_networkx(graph: KnowledgeGraph) -> nx.Graph:
    """Convert KnowledgeGraph to an undirected NetworkX Graph.

    Node attributes: label, type, community, plus scalar metadata.
    Parallel edges collapsed by keeping highest weight.
    """
    G = nx.Graph()
    for node_id, node in graph.nodes.items():
        attrs = {
            "label": node.label,
            "type": node.type,
            "community": node.community,
        }
        for k, v in node.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                attrs[k] = v
        G.add_node(node_id, **attrs)

    for edge in graph.edges:
        if edge.source not in graph.nodes or edge.target not in graph.nodes:
            continue
        if G.has_edge(edge.source, edge.target):
            if edge.weight <= G.edges[edge.source, edge.target].get("weight", 0):
                continue
        G.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation,
            weight=edge.weight,
            evidence=edge.evidence,
            paper_source=edge.paper_source,
        )
    return G


def annotate_communities(
    graph: KnowledgeGraph,
    communities: dict[int, list[str]],
) -> None:
    """Write community IDs from clustering back onto KnowledgeGraph nodes."""
    for cid, node_ids in communities.items():
        for node_id in node_ids:
            node = graph.get_node(node_id)
            if node:
                node.community = cid
