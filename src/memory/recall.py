"""上下文召回 -- 分析新论文时自动注入相关知识"""
from __future__ import annotations

from ..config import MEMORY_DIR
from .models import MemoryStore
from .embeddings import EmbeddingIndex
from .search import search_memory
from .prompts import CONTEXTUAL_RECALL_INTRO


def get_recall_context(
    paper_preview: str,
    store: MemoryStore | None = None,
    index: EmbeddingIndex | None = None,
    top_k: int = 10,
) -> str:
    """Given a paper preview (first ~2000 chars), retrieve relevant prior knowledge.

    Returns a formatted string to prepend to the analysis prompt,
    or empty string if no memories available.
    """
    if store is None:
        store = MemoryStore.load(MEMORY_DIR / "memory_store.json")
    if index is None:
        index = EmbeddingIndex.load(MEMORY_DIR)

    if len(index) == 0:
        return ""

    results = search_memory(paper_preview, store, index, top_k)
    if not results:
        return ""

    memory_lines = []
    for entry_id, score, content in results:
        if score < 0.2:  # skip low relevance
            continue
        entry = store.get(entry_id)
        if entry:
            sources = ", ".join(entry.source_papers[:2])
            memory_lines.append(f"- [{sources}] {content}")

    if not memory_lines:
        return ""

    return CONTEXTUAL_RECALL_INTRO.format(
        recalled_memories="\n".join(memory_lines[:10])
    )
