"""GraphML export -- opens in Gephi, yEd, Cytoscape."""
from __future__ import annotations

from pathlib import Path

import networkx as nx

from .models import KnowledgeGraph
from .nx_bridge import to_networkx


def to_graphml(graph: KnowledgeGraph, output_path: Path) -> Path:
    """Export KnowledgeGraph as GraphML with community and type attributes."""
    G = to_networkx(graph)
    communities = graph.get_communities()
    node_to_cid = {n: cid for cid, nodes in communities.items() for n in nodes}

    for node_id in G.nodes():
        G.nodes[node_id]["community"] = node_to_cid.get(node_id, -1)
        comm_label = graph.community_labels.get(node_to_cid.get(node_id, -1), "")
        G.nodes[node_id]["community_label"] = comm_label

    output_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, str(output_path))
    return output_path
