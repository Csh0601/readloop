"""从 analysis.md 提取结构化实体和关系"""
from __future__ import annotations

import re
from pathlib import Path

from ..client import LLMClient
from ..exceptions import ExtractionError
from .models import KnowledgeGraph, Node, Edge
from .prompts import EXTRACT_ENTITIES


def _slugify(text: str) -> str:
    """Create a deterministic slug from text."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    return s.strip("-")[:60]


def extract_from_analysis(
    analysis_text: str,
    paper_name: str,
    client: LLMClient,
) -> dict:
    """Extract structured entities from an analysis.md file.

    Returns raw extraction dict (JSON from LLM).
    """
    # Truncate if too long for extraction (analysis is ~350-400 lines, usually fine)
    if len(analysis_text) > 40000:
        analysis_text = analysis_text[:40000]

    prompt = EXTRACT_ENTITIES.format(analysis_text=analysis_text)
    try:
        return client.chat_json(prompt, max_tokens=4000)
    except (ValueError, Exception) as e:
        raise ExtractionError(f"Failed to extract entities from {paper_name}: {e}") from e


def extraction_to_graph(
    extraction: dict,
    paper_name: str,
    graph: KnowledgeGraph,
) -> None:
    """Convert extraction dict into graph nodes and edges, updating the graph in-place."""
    paper_info = extraction.get("paper", {})
    paper_slug = _slugify(paper_info.get("title", paper_name))
    paper_id = f"paper:{paper_slug}"

    # Add paper node
    graph.add_node(Node(
        id=paper_id,
        type="paper",
        label=paper_info.get("title", paper_name),
        metadata={
            "authors": paper_info.get("authors", []),
            "year": paper_info.get("year"),
            "venue": paper_info.get("venue", ""),
            "domain_tags": paper_info.get("domain_tags", []),
        },
    ))

    # Add concept nodes
    for c in extraction.get("concepts", []):
        c_id = f"concept:{_slugify(c['name'])}"
        graph.add_node(Node(
            id=c_id,
            type="concept",
            label=c["name"],
            metadata={"definition": c.get("definition", ""), "role": c.get("role", "")},
        ))

    # Add method nodes
    for m in extraction.get("methods", []):
        m_id = f"method:{_slugify(m['name'])}"
        graph.add_node(Node(
            id=m_id,
            type="method",
            label=m["name"],
            metadata={"description": m.get("description", ""), "type": m.get("type", "")},
        ))

    # Add dataset nodes
    for d in extraction.get("datasets", []):
        d_id = f"dataset:{_slugify(d['name'])}"
        graph.add_node(Node(
            id=d_id,
            type="dataset",
            label=d["name"],
            metadata={"domain": d.get("domain", "")},
        ))

    # Add metric nodes
    for met in extraction.get("metrics", []):
        met_id = f"metric:{_slugify(met['name'])}"
        graph.add_node(Node(
            id=met_id,
            type="metric",
            label=met["name"],
            metadata={"description": met.get("description", "")},
        ))

    # Add relationships as edges
    for rel in extraction.get("relationships", []):
        src_type = rel.get("source_type", "concept")
        tgt_type = rel.get("target_type", "concept")
        src_id = f"{src_type}:{_slugify(rel['source'])}"
        tgt_id = f"{tgt_type}:{_slugify(rel['target'])}"
        graph.add_edge(Edge(
            source=src_id,
            target=tgt_id,
            relation=rel.get("relation", "uses"),
            weight=1.0,
            evidence=rel.get("evidence", ""),
            paper_source=paper_id,
        ))

    # Add implicit paper->method/concept edges
    for m in extraction.get("methods", []):
        m_id = f"method:{_slugify(m['name'])}"
        rel = "proposes" if m.get("type") == "proposed" else "uses"
        graph.add_edge(Edge(
            source=paper_id, target=m_id, relation=rel,
            paper_source=paper_id,
        ))

    for c in extraction.get("concepts", []):
        c_id = f"concept:{_slugify(c['name'])}"
        if c.get("role") == "core":
            graph.add_edge(Edge(
                source=paper_id, target=c_id, relation="proposes",
                paper_source=paper_id,
            ))
