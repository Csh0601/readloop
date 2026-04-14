"""Graph analysis: god nodes, surprising connections, research questions.

Adapted from graphify/analyze.py for academic paper knowledge graphs.
"""
from __future__ import annotations

import networkx as nx

from .models import KnowledgeGraph
from .nx_bridge import to_networkx


def god_nodes(graph: KnowledgeGraph, top_n: int = 10) -> list[dict]:
    """Return top-N most-connected nodes (core concepts/papers)."""
    G = to_networkx(graph)
    degree = dict(G.degree())
    sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)

    result = []
    for node_id, deg in sorted_nodes:
        if len(result) >= top_n:
            break
        node = graph.get_node(node_id)
        result.append({
            "id": node_id,
            "label": node.label if node else node_id,
            "type": node.type if node else "unknown",
            "edges": deg,
            "community": node.community if node else None,
        })
    return result


def surprising_connections(
    graph: KnowledgeGraph,
    communities: dict[int, list[str]],
    top_n: int = 5,
) -> list[dict]:
    """Find cross-community edges -- connections bridging research themes.

    Scoring: cross-community +3, contradicts +4, compares +2,
    low weight +1, peripheral-to-hub +1.
    """
    G = to_networkx(graph)
    node_to_cid = {n: cid for cid, nodes in communities.items() for n in nodes}

    candidates = []
    for u, v, data in G.edges(data=True):
        cid_u = node_to_cid.get(u)
        cid_v = node_to_cid.get(v)
        if cid_u is None or cid_v is None or cid_u == cid_v:
            continue

        score = 3  # cross-community base
        reasons: list[str] = []

        label_u = graph.community_labels.get(cid_u, f"Community {cid_u}")
        label_v = graph.community_labels.get(cid_v, f"Community {cid_v}")
        reasons.append(f"bridges '{label_u}' and '{label_v}'")

        relation = data.get("relation", "")
        if relation == "contradicts":
            score += 4
            reasons.append("contradictory finding")
        elif relation == "compares":
            score += 2
            reasons.append("comparison between distant themes")
        elif relation == "shared_concept":
            score += 1
            reasons.append("unexpected shared concept")

        weight = data.get("weight", 1.0)
        if weight < 0.5:
            score += 1
            reasons.append(f"low confidence ({weight:.1f})")

        deg_u, deg_v = G.degree(u), G.degree(v)
        if min(deg_u, deg_v) <= 2 and max(deg_u, deg_v) >= 5:
            score += 1
            u_node = graph.get_node(u)
            v_node = graph.get_node(v)
            peripheral = (u_node.label if u_node else u) if deg_u <= 2 else (v_node.label if v_node else v)
            hub = (v_node.label if v_node else v) if deg_u <= 2 else (u_node.label if u_node else u)
            reasons.append(f"peripheral '{peripheral}' reaches hub '{hub}'")

        u_node = graph.get_node(u)
        v_node = graph.get_node(v)
        candidates.append({
            "_score": score,
            "source": u_node.label if u_node else u,
            "source_type": u_node.type if u_node else "unknown",
            "target": v_node.label if v_node else v,
            "target_type": v_node.type if v_node else "unknown",
            "relation": relation,
            "evidence": data.get("evidence", ""),
            "why": "; ".join(reasons),
        })

    candidates.sort(key=lambda x: x["_score"], reverse=True)
    for c in candidates:
        c.pop("_score")

    if not candidates and G.number_of_edges() > 0:
        betweenness = nx.edge_betweenness_centrality(G)
        top_edges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [
            {
                "source": (graph.get_node(u).label if graph.get_node(u) else u),
                "target": (graph.get_node(v).label if graph.get_node(v) else v),
                "relation": G.edges[u, v].get("relation", ""),
                "evidence": G.edges[u, v].get("evidence", ""),
                "why": f"High structural bridging (betweenness={s:.3f})",
            }
            for (u, v), s in top_edges
        ]

    return candidates[:top_n]


def suggest_questions(
    graph: KnowledgeGraph,
    communities: dict[int, list[str]],
    top_n: int = 7,
) -> list[dict]:
    """Generate research questions from graph structure.

    Categories: low-confidence edges, bridge nodes, isolated nodes,
    low-cohesion communities, missing method-dataset evaluations.
    """
    G = to_networkx(graph)
    node_to_cid = {n: cid for cid, nodes in communities.items() for n in nodes}
    questions: list[dict] = []

    # 1. Low-weight edges
    for u, v, data in G.edges(data=True):
        if data.get("weight", 1.0) < 0.5:
            u_node, v_node = graph.get_node(u), graph.get_node(v)
            ul = u_node.label if u_node else u
            vl = v_node.label if v_node else v
            rel = data.get("relation", "related to")
            questions.append({
                "type": "low_confidence",
                "question": f"Is the '{rel}' relationship between '{ul}' and '{vl}' accurate?",
                "why": f"Edge weight {data.get('weight', 0):.1f} -- low confidence.",
            })

    # 2. Bridge nodes
    if G.number_of_edges() > 0:
        betweenness = nx.betweenness_centrality(G)
        bridges = sorted(
            [(n, s) for n, s in betweenness.items() if s > 0],
            key=lambda x: x[1], reverse=True,
        )[:3]
        for node_id, score in bridges:
            node = graph.get_node(node_id)
            label = node.label if node else node_id
            cid = node_to_cid.get(node_id)
            comm_label = graph.community_labels.get(cid, f"Community {cid}") if cid is not None else "unknown"
            neighbors = list(G.neighbors(node_id))
            neighbor_comms = {node_to_cid.get(n) for n in neighbors if node_to_cid.get(n) != cid}
            neighbor_comms.discard(None)
            if neighbor_comms:
                other_labels = [graph.community_labels.get(c, f"Community {c}") for c in neighbor_comms]
                questions.append({
                    "type": "bridge_node",
                    "question": f"Why does '{label}' connect '{comm_label}' to {', '.join(repr(lbl) for lbl in other_labels)}?",
                    "why": f"High betweenness centrality ({score:.3f}) -- cross-theme bridge.",
                })

    # 3. Isolated/weakly-connected nodes
    isolated = [n for n in G.nodes() if G.degree(n) <= 1]
    if isolated:
        labels = [graph.get_node(n).label if graph.get_node(n) else n for n in isolated[:3]]
        questions.append({
            "type": "isolated_nodes",
            "question": f"What connects {', '.join(repr(l) for l in labels)} to the rest of the research?",
            "why": f"{len(isolated)} weakly-connected nodes -- possible literature gaps.",
        })

    # 4. Low-cohesion communities
    from .cluster import cohesion_score as _coh
    for cid, nodes in communities.items():
        score = _coh(G, nodes)
        if score < 0.15 and len(nodes) >= 5:
            label = graph.community_labels.get(cid, f"Community {cid}")
            questions.append({
                "type": "low_cohesion",
                "question": f"Should '{label}' be split into more specific sub-themes?",
                "why": f"Cohesion {score:.2f} -- nodes are weakly related internally.",
            })

    # 5. Missing method-dataset evaluations
    methods = graph.find_nodes_by_type("method")
    datasets = graph.find_nodes_by_type("dataset")
    evaluated_pairs = {
        (e.source, e.target) for e in graph.edges if e.relation == "evaluated_on"
    }
    for m in methods[:5]:
        for d in datasets[:5]:
            if (m.id, d.id) not in evaluated_pairs and (d.id, m.id) not in evaluated_pairs:
                questions.append({
                    "type": "missing_evaluation",
                    "question": f"Has '{m.label}' been evaluated on '{d.label}'?",
                    "why": "No evaluated_on edge between this method-dataset pair.",
                })

    return questions[:top_n]
