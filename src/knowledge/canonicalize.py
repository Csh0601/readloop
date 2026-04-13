"""概念规范化 — 基于 embedding 相似度合并同义节点"""
from __future__ import annotations

import os

import numpy as np

from ..memory.embeddings import embed_texts
from .models import KnowledgeGraph, Edge

MERGE_THRESHOLD = float(os.environ.get("READLOOP_MERGE_THRESHOLD", "0.90"))


def canonicalize_concepts(
    graph: KnowledgeGraph, dry_run: bool = False
) -> dict[str, str]:
    """Merge synonymous concept/method nodes by embedding similarity.

    Returns {old_id: canonical_id} mapping.
    dry_run=True returns the mapping without modifying the graph.
    """
    merge_types = ("concept", "method")
    nodes = [n for n in graph.nodes.values() if n.type in merge_types]
    if len(nodes) < 2:
        return {}

    labels = [n.label for n in nodes]
    vecs = embed_texts(labels)  # (N, 384), normalized
    sim_matrix = vecs @ vecs.T

    # Union-Find for grouping
    parent = list(range(len(nodes)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if sim_matrix[i, j] > MERGE_THRESHOLD:
                union(i, j)

    # Pre-build edge count cache to avoid O(N*E) in canonical selection
    edge_counts: dict[str, int] = {}
    for e in graph.edges:
        edge_counts[e.source] = edge_counts.get(e.source, 0) + 1
        edge_counts[e.target] = edge_counts.get(e.target, 0) + 1

    # Group by root, pick canonical (most edges; tie-break: longer label)
    groups: dict[int, list[int]] = {}
    for i in range(len(nodes)):
        root = find(i)
        groups.setdefault(root, []).append(i)

    remap: dict[str, str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        best = max(
            members,
            key=lambda i: (edge_counts.get(nodes[i].id, 0), len(nodes[i].label)),
        )
        canonical_id = nodes[best].id
        for m in members:
            if m != best:
                remap[nodes[m].id] = canonical_id

    if not dry_run:
        _apply_merge(graph, remap)
    return remap


def preview_merges(graph: KnowledgeGraph) -> list[dict]:
    """Dry-run: return list of proposed merges for human review."""
    remap = canonicalize_concepts(graph, dry_run=True)
    result = []
    for old_id, new_id in remap.items():
        old_node = graph.get_node(old_id)
        new_node = graph.get_node(new_id)
        if old_node and new_node:
            result.append({
                "merge": old_node.label,
                "into": new_node.label,
                "old_id": old_id,
                "new_id": new_id,
            })
    return result


def prune_hapax_nodes(graph: KnowledgeGraph) -> int:
    """Remove concept/method nodes that appear in only 1 paper and have <= 1 edge.

    Returns count of pruned nodes.
    """
    to_remove = []
    for node in list(graph.nodes.values()):
        if node.type not in ("concept", "method"):
            continue
        edges = graph.get_edges_for_node(node.id)
        if len(edges) <= 1:
            paper_sources = {e.paper_source for e in edges if e.paper_source}
            if len(paper_sources) <= 1:
                to_remove.append(node.id)

    remove_set = set(to_remove)
    graph.edges = [
        e for e in graph.edges
        if e.source not in remove_set and e.target not in remove_set
    ]
    for node_id in to_remove:
        del graph.nodes[node_id]

    return len(to_remove)


def _resolve(node_id: str, remap: dict[str, str]) -> str:
    """Follow remap chain to canonical ID."""
    while node_id in remap:
        node_id = remap[node_id]
    return node_id


def _apply_merge(graph: KnowledgeGraph, remap: dict[str, str]) -> None:
    """Redirect edges from merged nodes to canonical, clean up.

    Creates new Edge objects instead of mutating in-place.
    Uses _resolve() to follow any remap chains safely.
    """
    # Rebuild edges with resolved IDs (immutable approach)
    new_edges = [
        Edge(
            source=_resolve(e.source, remap),
            target=_resolve(e.target, remap),
            relation=e.relation,
            weight=e.weight,
            evidence=e.evidence,
            paper_source=e.paper_source,
        )
        for e in graph.edges
    ]

    # Remove self-loops
    new_edges = [e for e in new_edges if e.source != e.target]

    # Deduplicate edges (same source + target + relation)
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for e in new_edges:
        key = (e.source, e.target, e.relation)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    graph.edges = unique

    # Remove merged nodes
    for old_id in remap:
        graph.nodes.pop(old_id, None)
