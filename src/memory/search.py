"""语义搜索 + LLM 合成回答

Hybrid scoring: embedding similarity (70%) + keyword match (15%)
+ domain tag match (10%) + confidence boost (5%).

Adapted from graphify/serve.py multi-strategy scoring pattern.
"""
from __future__ import annotations

import hashlib
import logging

from ..client import LLMClient

_log = logging.getLogger(__name__)
from ..config import MEMORY_DIR
from .models import MemoryStore, MemoryEntry
from .embeddings import EmbeddingIndex
from .prompts import ANSWER_QUERY

# Token budget: ~3 chars per token, cap context at 6000 tokens
_TOKEN_BUDGET = 6000
_CHARS_PER_TOKEN = 3


def _hybrid_score(
    entry: MemoryEntry,
    embedding_sim: float,
    query_terms: list[str],
) -> float:
    """Combine embedding similarity with keyword/tag/confidence signals."""
    # Embedding similarity (primary signal)
    emb_score = embedding_sim * 0.70

    # Keyword match in content
    content_lower = entry.content.lower()
    if query_terms:
        keyword_hits = sum(1 for t in query_terms if t in content_lower)
        keyword_score = min(keyword_hits / len(query_terms), 1.0) * 0.15
    else:
        keyword_score = 0.0

    # Domain tag match
    tag_score = 0.0
    if query_terms and entry.domain_tags:
        tags_lower = [t.lower() for t in entry.domain_tags]
        tag_hits = sum(1 for t in query_terms if any(t in tag for tag in tags_lower))
        tag_score = min(tag_hits / len(query_terms), 1.0) * 0.10

    # Confidence boost
    conf_score = entry.confidence * 0.05

    return emb_score + keyword_score + tag_score + conf_score


def search_memory(
    query: str,
    store: MemoryStore,
    index: EmbeddingIndex,
    top_k: int = 20,
) -> list[tuple[str, float, str]]:
    """Search memory with hybrid scoring.

    Returns: [(entry_id, hybrid_score, content), ...]
    """
    if len(index) == 0:
        return []

    # Get embedding-based candidates (fetch extra for re-ranking)
    candidates = index.search(query, k=min(top_k * 2, len(index)))
    query_terms = [t.lower() for t in query.split() if len(t) >= 2]

    scored = []
    for entry_id, emb_sim in candidates:
        entry = store.get(entry_id)
        if not entry:
            continue
        hybrid = _hybrid_score(entry, emb_sim, query_terms)
        scored.append((entry_id, hybrid, entry.content))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def ask_with_memory(
    query: str,
    client: LLMClient,
    store: MemoryStore | None = None,
    index: EmbeddingIndex | None = None,
    top_k: int = 20,
) -> str:
    """Answer a query using memory store + LLM synthesis.

    Applies token budget to avoid sending too much context.
    Saves Q&A result as new insight memory (feedback loop from Graphify).
    """
    if store is None:
        store = MemoryStore.load(MEMORY_DIR / "memory_store.json")
    if index is None:
        index = EmbeddingIndex.load(MEMORY_DIR)

    if len(index) == 0:
        return "Memory store is empty. Run --build-memory first."

    results = search_memory(query, store, index, top_k)
    if not results:
        return "No relevant memories found."

    # Format with token budget
    memory_lines = []
    char_budget = _TOKEN_BUDGET * _CHARS_PER_TOKEN
    used = 0
    included = 0
    for entry_id, score, content in results:
        entry = store.get(entry_id)
        if not entry:
            continue
        sources = ", ".join(entry.source_papers)
        line = f"- [{entry.type}] (from: {sources}, relevance: {score:.2f}): {content}"
        if used + len(line) > char_budget:
            break
        memory_lines.append(line)
        used += len(line)
        included += 1

    prompt = ANSWER_QUERY.format(
        query=query,
        memories="\n".join(memory_lines),
    )

    answer = client.chat(prompt, max_tokens=4000)

    # Feedback loop: save Q&A as insight memory (from Graphify pattern)
    _save_qa_as_memory(query, answer, store, index)

    return answer


def _save_qa_as_memory(
    query: str,
    answer: str,
    store: MemoryStore,
    index: EmbeddingIndex,
) -> None:
    """Save synthesized Q&A as a new insight memory entry."""
    if len(query) > 1000:
        query = query[:1000]
    content = f"Q: {query}\nA: {answer[:500]}"
    entry_id = hashlib.sha256(f"qa:{query}".encode()).hexdigest()[:16]

    if store.get(entry_id):
        return  # already exists

    entry = MemoryEntry(
        id=entry_id,
        type="insight",
        content=content,
        source_papers=["synthesized_qa"],
        domain_tags=[],
        confidence=0.7,
    )
    store.add(entry)
    index.add(entry_id, content)

    try:
        store.save(MEMORY_DIR / "memory_store.json")
        index.save(MEMORY_DIR)
    except Exception:
        _log.warning("Failed to persist Q&A memory", exc_info=True)
