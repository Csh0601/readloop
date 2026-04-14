"""自动综述生成 -- 基于知识图谱 + 记忆"""
from __future__ import annotations

import re
from pathlib import Path

from ..client import LLMClient
from ..config import REVIEWS_DIR, MEMORY_DIR, GRAPH_DIR
from ..knowledge.models import KnowledgeGraph
from ..memory.models import MemoryStore
from ..memory.embeddings import EmbeddingIndex
from ..memory.search import search_memory


REVIEW_PROMPT = """你是一位资深 AI 研究员，正在撰写一篇关于 "{topic}" 的文献综述。

以下是从知识库中检索到的相关论文知识:

{knowledge}

请撰写一篇结构化的文献综述（中文），包含:

# {topic} — 文献综述

## 1. 综述概要
（2-3 段概述该主题的研究背景、重要性和发展脉络）

## 2. 技术路线分类
（按方法类型/思路对相关论文分组）

| 类别 | 代表论文 | 核心方法 | 关键特点 |
|------|---------|---------|---------|
| | | | |

## 3. 方法演进时间线

```mermaid
graph LR
    A[早期方法] --> B[改进方法] --> C[最新方法]
```

## 4. 核心方法对比

| 维度 | 方法A | 方法B | 方法C |
|------|------|------|------|
| | | | |

## 5. 关键发现与共识
（该领域目前达成了哪些共识？）

## 6. 开放问题与争议
（哪些问题尚未解决？不同论文有何分歧？）

## 7. 未来研究方向
（基于以上分析，该主题的高价值研究方向是什么？）

## 8. 参考论文列表

要求:
- 所有论断必须有论文来源
- 对比分析要具体，不要泛泛而谈
- 图表必须基于实际论文内容
"""


def generate_review(
    topic: str,
    client: LLMClient,
) -> Path:
    """Generate a literature review on a given topic."""
    # Load knowledge sources
    store = MemoryStore.load(MEMORY_DIR / "memory_store.json")
    index = EmbeddingIndex.load(MEMORY_DIR)
    graph = KnowledgeGraph.load(GRAPH_DIR / "graph.json")

    # Search for relevant knowledge
    results = search_memory(topic, store, index, top_k=40)

    # Format knowledge
    knowledge_parts = []
    for entry_id, score, content in results:
        entry = store.get(entry_id)
        if entry and score > 0.15:
            sources = ", ".join(entry.source_papers[:2])
            knowledge_parts.append(f"- [{entry.type}] ({sources}): {content}")

    # Add graph context
    graph_context = []
    for node in graph.find_nodes_by_type("method"):
        edges = graph.get_edges_for_node(node.id)
        if edges:
            relations = "; ".join(f"{e.relation}->{e.target}" for e in edges[:3])
            graph_context.append(f"- Method '{node.label}': {relations}")

    knowledge = "\n".join(knowledge_parts[:50])
    if graph_context:
        knowledge += "\n\nGraph relationships:\n" + "\n".join(graph_context[:20])

    prompt = REVIEW_PROMPT.format(topic=topic, knowledge=knowledge)
    review = client.chat(prompt, max_tokens=8000)

    # Save
    slug = re.sub(r'[\\/:*?"<>|]', '_', topic[:50]).strip()
    output_dir = REVIEWS_DIR / slug
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "review.md"
    output_path.write_text(review, encoding="utf-8")

    return output_path
