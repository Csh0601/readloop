"""知识图谱数据模型"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path


@dataclass
class Node:
    id: str               # "paper:a-mem", "concept:zettelkasten-memory"
    type: str             # paper | concept | method | dataset | metric
    label: str            # human-readable name
    metadata: dict = field(default_factory=dict)
    community: int | None = None  # Leiden community ID (set by cluster step)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


@dataclass
class Edge:
    source: str           # node id
    target: str           # node id
    relation: str         # proposes | uses | improves | compares | contradicts | complements | shared_concept
    weight: float = 1.0   # confidence 0-1
    evidence: str = ""    # brief justification
    paper_source: str = ""  # which paper produced this edge

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Edge:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


@dataclass
class KnowledgeGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    version: int = 1
    community_labels: dict[int, str] = field(default_factory=dict)
    community_cohesion: dict[int, float] = field(default_factory=dict)

    # --- Node ops ---

    def add_node(self, node: Node) -> bool:
        """Add node if not exists. Returns True if added."""
        if node.id in self.nodes:
            return False
        self.nodes[node.id] = node
        return True

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def find_nodes_by_type(self, node_type: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]

    # --- Edge ops ---

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    def get_edges_for_node(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id or e.target == node_id]

    def get_edges_by_relation(self, relation: str) -> list[Edge]:
        return [e for e in self.edges if e.relation == relation]

    def get_communities(self) -> dict[int, list[str]]:
        """Return {community_id: [node_ids]} from node annotations."""
        result: dict[int, list[str]] = {}
        for node_id, node in self.nodes.items():
            if node.community is not None:
                result.setdefault(node.community, []).append(node_id)
        return result

    # --- Stats ---

    def stats(self) -> dict:
        type_counts = {}
        for n in self.nodes.values():
            type_counts[n.type] = type_counts.get(n.type, 0) + 1
        rel_counts = {}
        for e in self.edges:
            rel_counts[e.relation] = rel_counts.get(e.relation, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "edge_relations": rel_counts,
        }

    # --- Serialization ---

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self.version,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "community_labels": {str(k): v for k, v in self.community_labels.items()},
            "community_cohesion": {str(k): v for k, v in self.community_cohesion.items()},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> KnowledgeGraph:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        graph = cls(version=data.get("version", 1))
        for k, v in data.get("nodes", {}).items():
            graph.nodes[k] = Node.from_dict(v)
        for e in data.get("edges", []):
            graph.edges.append(Edge.from_dict(e))
        graph.community_labels = {
            int(k): v for k, v in data.get("community_labels", {}).items()
        }
        graph.community_cohesion = {
            int(k): v for k, v in data.get("community_cohesion", {}).items()
        }
        return graph
