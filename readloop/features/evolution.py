"""概念演进追踪"""
from __future__ import annotations

from pathlib import Path

from ..client import LLMClient
from ..config import EVOLUTION_DIR, GRAPH_DIR
from ..knowledge.models import KnowledgeGraph


EVOLUTION_PROMPT = """你是研究方法论专家。分析以下概念在不同论文中的演进过程。

概念名称: {concept_name}

该概念在以下论文中被提及:
{paper_mentions}

请输出 Markdown 分析报告:

# 概念演进: {concept_name}

## 1. 概念定义演化
（该概念的定义在不同论文中如何变化？）

## 2. 演进时间线

```mermaid
graph LR
    A["早期定义<br/>论文A"] --> B["改进定义<br/>论文B"] --> C["最新理解<br/>论文C"]
```

## 3. 使用方式变化
（早期怎么用？现在怎么用？发生了什么转变？）

## 4. 相关概念分裂/合并
（这个概念是否分化出子概念？是否与其他概念合并？）

## 5. 趋势预测
（基于演进趋势，该概念未来可能如何发展？）
"""


def track_concept(
    concept_name: str,
    client: LLMClient,
) -> Path:
    """Track how a concept evolves across papers."""
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")

    # Find the concept node
    target = None
    for node in graph.find_nodes_by_type("concept"):
        if concept_name.lower() in node.label.lower():
            target = node
            break

    if not target:
        raise ValueError(f"Concept '{concept_name}' not found in graph")

    # Find papers that reference this concept
    edges = graph.get_edges_for_node(target.id)
    paper_ids = set()
    for e in edges:
        if e.source.startswith("paper:"):
            paper_ids.add(e.source)
        if e.target.startswith("paper:"):
            paper_ids.add(e.target)

    # Build paper mentions
    mentions = []
    for pid in sorted(paper_ids):
        pnode = graph.get_node(pid)
        if pnode:
            year = pnode.metadata.get("year", "?")
            paper_edges = [
                e for e in edges
                if e.source == pid or e.target == pid
            ]
            relations = ", ".join(e.relation for e in paper_edges)
            mentions.append(f"- {pnode.label} ({year}): {relations}")

    if len(mentions) < 2:
        raise ValueError(f"Concept '{concept_name}' only in {len(mentions)} paper(s), need 2+")

    prompt = EVOLUTION_PROMPT.format(
        concept_name=target.label,
        paper_mentions="\n".join(mentions),
    )
    result = client.chat(prompt, max_tokens=4000)

    import re
    slug = re.sub(r'[\\/:*?"<>|]', '_', concept_name[:50]).strip()
    EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EVOLUTION_DIR / f"{slug}.md"
    output_path.write_text(result, encoding="utf-8")
    return output_path
