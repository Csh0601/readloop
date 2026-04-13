"""Community detection for ReadLoop knowledge graphs.

Adapted from graphify/cluster.py. Uses Leiden (graspologic) with
Louvain (networkx) fallback. Adds research-domain community labeling.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import logging
import sys

import networkx as nx

_log = logging.getLogger(__name__)

from .models import KnowledgeGraph
from .nx_bridge import annotate_communities, to_networkx


# ---------------------------------------------------------------------------
# Core clustering (from Graphify, logic preserved)
# ---------------------------------------------------------------------------

def _suppress_output():
    """Suppress stdout during graspologic calls (ANSI issue on Windows)."""
    return contextlib.redirect_stdout(io.StringIO())


def _partition(G: nx.Graph) -> dict[str, int]:
    """Leiden with graspologic, Louvain fallback."""
    try:
        from graspologic.partition import leiden

        old_stderr = sys.stderr
        try:
            sys.stderr = io.StringIO()
            with _suppress_output():
                result = leiden(G)
        finally:
            sys.stderr = old_stderr
        return result
    except ImportError:
        pass

    kwargs: dict = {"seed": 42, "threshold": 1e-4}
    if "max_level" in inspect.signature(nx.community.louvain_communities).parameters:
        kwargs["max_level"] = 10
    communities = nx.community.louvain_communities(G, **kwargs)
    return {node: cid for cid, nodes in enumerate(communities) for node in nodes}


_MAX_COMMUNITY_FRACTION = 0.25
_MIN_SPLIT_SIZE = 10


def _cluster_nx(G: nx.Graph) -> dict[int, list[str]]:
    """Run clustering on a NetworkX graph. Returns {cid: [node_ids]}."""
    if G.number_of_nodes() == 0:
        return {}
    if G.is_directed():
        G = G.to_undirected()
    if G.number_of_edges() == 0:
        return {i: [n] for i, n in enumerate(sorted(G.nodes))}

    isolates = [n for n in G.nodes() if G.degree(n) == 0]
    connected_nodes = [n for n in G.nodes() if G.degree(n) > 0]
    connected = G.subgraph(connected_nodes)

    raw: dict[int, list[str]] = {}
    if connected.number_of_nodes() > 0:
        partition = _partition(connected)
        for node, cid in partition.items():
            raw.setdefault(cid, []).append(node)

    next_cid = max(raw.keys(), default=-1) + 1
    for node in isolates:
        raw[next_cid] = [node]
        next_cid += 1

    max_size = max(_MIN_SPLIT_SIZE, int(G.number_of_nodes() * _MAX_COMMUNITY_FRACTION))
    final: list[list[str]] = []
    for nodes in raw.values():
        if len(nodes) > max_size:
            final.extend(_split_community(G, nodes))
        else:
            final.append(nodes)

    final.sort(key=len, reverse=True)
    return {i: sorted(nodes) for i, nodes in enumerate(final)}


def _split_community(G: nx.Graph, nodes: list[str]) -> list[list[str]]:
    """Split oversized community with a second clustering pass."""
    subgraph = G.subgraph(nodes)
    if subgraph.number_of_edges() == 0:
        return [[n] for n in sorted(nodes)]
    try:
        sub_partition = _partition(subgraph)
        sub_communities: dict[int, list[str]] = {}
        for node, cid in sub_partition.items():
            sub_communities.setdefault(cid, []).append(node)
        if len(sub_communities) <= 1:
            return [sorted(nodes)]
        return [sorted(v) for v in sub_communities.values()]
    except Exception as exc:
        _log.warning("Sub-community split failed, keeping original: %s", exc)
        return [sorted(nodes)]


def cohesion_score(G: nx.Graph, community_nodes: list[str]) -> float:
    """Ratio of actual intra-community edges to maximum possible."""
    n = len(community_nodes)
    if n <= 1:
        return 1.0
    subgraph = G.subgraph(community_nodes)
    actual = subgraph.number_of_edges()
    possible = n * (n - 1) / 2
    return round(actual / possible, 2) if possible > 0 else 0.0


def score_all(G: nx.Graph, communities: dict[int, list[str]]) -> dict[int, float]:
    """Compute cohesion scores for all communities."""
    return {cid: cohesion_score(G, nodes) for cid, nodes in communities.items()}


# ---------------------------------------------------------------------------
# ReadLoop high-level API
# ---------------------------------------------------------------------------

def cluster_graph(graph: KnowledgeGraph) -> dict[int, list[str]]:
    """Run community detection on a ReadLoop KnowledgeGraph.

    Returns {community_id: [node_ids]}. Annotates graph nodes in-place.
    """
    G = to_networkx(graph)
    communities = _cluster_nx(G)
    annotate_communities(graph, communities)
    graph.community_cohesion = score_all(G, communities)
    return communities


def label_communities(
    graph: KnowledgeGraph,
    communities: dict[int, list[str]],
) -> dict[int, str]:
    """Generate human-readable labels for communities.

    Strategy: name after the dominant concept or paper theme.
    """
    labels: dict[int, str] = {}

    for cid, node_ids in communities.items():
        nodes = [graph.get_node(nid) for nid in node_ids if graph.get_node(nid)]
        if not nodes:
            labels[cid] = f"Community {cid}"
            continue

        papers = [n for n in nodes if n.type == "paper"]
        concepts = [n for n in nodes if n.type == "concept"]
        methods = [n for n in nodes if n.type == "method"]

        if papers and concepts:
            concept_edge_counts = [
                (c, len([
                    e for e in graph.get_edges_for_node(c.id)
                    if e.source in node_ids or e.target in node_ids
                ]))
                for c in concepts
            ]
            top = max(concept_edge_counts, key=lambda x: x[1])[0]
            labels[cid] = f"{top.label[:40]} Research"
        elif papers:
            if len(papers) == 1:
                labels[cid] = papers[0].label[:40]
            else:
                labels[cid] = f"Paper Cluster ({len(papers)} papers)"
        elif methods:
            top = max(methods, key=lambda m: len(graph.get_edges_for_node(m.id)))
            labels[cid] = f"{top.label[:40]} Methods"
        elif concepts:
            top = max(concepts, key=lambda c: len(graph.get_edges_for_node(c.id)))
            labels[cid] = top.label[:40]
        else:
            labels[cid] = f"Community {cid}"

    return labels
