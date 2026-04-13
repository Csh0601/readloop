"""研究提案生成 -- 基于知识图谱空白"""
from __future__ import annotations

from pathlib import Path

from ..client import LLMClient
from ..config import PROPOSALS_DIR, GRAPH_DIR
from ..knowledge.models import KnowledgeGraph


PROPOSAL_PROMPT = """你是一位经验丰富的 AI 研究导师。基于以下知识图谱中发现的研究空白，生成具体可行的研究提案。

{context}

请生成 3-5 个研究提案，按价值排序。每个提案严格使用以下格式:

# 研究提案

## 提案 1: [标题]

### 问题陈述
（要解决什么问题？为什么当前没有好的解决方案？）

### 方法建议
（具体怎么做？可以组合哪些已有方法？）

### 技术方案概述

```mermaid
graph TD
    A[输入] --> B[方法步骤1]
    B --> C[方法步骤2]
    C --> D[预期输出]
```

### 预期贡献
（做完后对领域有什么贡献？）

### 可行性评估
| 维度 | 评估 |
|------|------|
| 新颖性 | 高/中/低 + 理由 |
| 技术可行性 | 高/中/低 + 理由 |
| 影响力 | 高/中/低 + 理由 |

### 相关论文
（图谱中最相关的 2-3 篇论文及其关系）

---

## 提案 2: [标题]
...
"""


def generate_proposals(
    client: LLMClient,
    topic: str | None = None,
) -> Path:
    """Generate research proposals from knowledge graph gaps."""
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")
    stats = graph.stats()

    # Build context
    context_parts = [f"Graph stats: {stats}"]

    # List methods and their connections
    methods = graph.find_nodes_by_type("method")
    context_parts.append("\nMethods in the graph:")
    for m in methods:
        edges = graph.get_edges_for_node(m.id)
        relations = "; ".join(f"{e.relation}->{e.target}" for e in edges[:5])
        context_parts.append(f"  - {m.label}: {relations}")

    # List concepts
    concepts = graph.find_nodes_by_type("concept")
    context_parts.append("\nKey concepts:")
    for c in concepts[:30]:
        defn = c.metadata.get("definition", "")[:80]
        context_parts.append(f"  - {c.label}: {defn}")

    # List shared_concept edges (cross-paper connections)
    shared = graph.get_edges_by_relation("shared_concept")
    if shared:
        context_parts.append(f"\nCross-paper shared concepts ({len(shared)} connections):")
        for e in shared[:20]:
            context_parts.append(f"  - {e.source} <-> {e.target}: {e.evidence}")

    if topic:
        context_parts.append(f"\nUser requested focus: {topic}")

    context = "\n".join(context_parts)
    prompt = PROPOSAL_PROMPT.format(context=context)
    result = client.chat(prompt, max_tokens=8000)

    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROPOSALS_DIR / "proposals.md"
    output_path.write_text(result, encoding="utf-8")
    return output_path
