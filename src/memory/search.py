"""语义搜索 + LLM 合成回答

Hybrid scoring: embedding similarity (70%) + keyword match (20%)
+ domain tag match (10%), with multiplicative confidence adjustment (0.85-1.0).

Adapted from graphify/serve.py multi-strategy scoring pattern.
"""
from __future__ import annotations

import logging

from ..client import LLMClient
from ..utils import make_entry_id

_log = logging.getLogger(__name__)
from ..config import MEMORY_DIR
from .models import MemoryStore, MemoryEntry
from .embeddings import EmbeddingIndex
from .prompts import ANSWER_QUERY

# Token budget: ~3 chars per token, cap context at 6000 tokens
_TOKEN_BUDGET = 6000
_CHARS_PER_TOKEN = 3


_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "our", "we",
    "are", "was", "is", "of", "in", "to", "a", "an", "on",
    "by", "from", "as", "it", "be", "has", "have", "been",
})


def _hybrid_score(
    entry: MemoryEntry,
    embedding_sim: float,
    query_terms: list[str],
) -> float:
    """Combine embedding similarity with keyword/tag/confidence signals.

    Scoring:
    - Embedding (70%): ReLU-clamped cosine similarity
    - Keyword (20%): term overlap with stopword filtering, capped at 30 terms
    - Tag (10%): domain tag overlap
    - Confidence: multiplicative adjustment (0.85-1.0), not additive
    """
    emb = max(0.0, embedding_sim)

    effective_terms = [t for t in query_terms if len(t) >= 3 and t not in _STOPWORDS][:30]

    if effective_terms:
        content_lower = entry.content.lower()
        keyword_hits = sum(1 for t in effective_terms if t in content_lower)
        keyword = min(keyword_hits / len(effective_terms), 1.0)
    else:
        keyword = 0.0

    tag = 0.0
    if effective_terms and entry.domain_tags:
        tags_lower = [t.lower() for t in entry.domain_tags]
        tag_hits = sum(1 for t in effective_terms if any(t in tg for tg in tags_lower))
        tag = min(tag_hits / len(effective_terms), 1.0)

    score = 0.70 * emb + 0.20 * keyword + 0.10 * tag
    score *= (0.85 + 0.15 * entry.confidence)

    return score


def search_memory(
    query: str,
    store: MemoryStore,
    index: EmbeddingIndex,
    top_k: int = 20,
    include_insights: bool = False,
) -> list[tuple[str, float, str]]:
    """Search memory with hybrid scoring.

    Args:
        include_insights: If False (default), excludes synthesized Q&A insights
            from results to prevent memory amplification.

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
        if not include_insights and entry.type == "insight":
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
        prefix = "SYNTHESIZED " if entry.type == "insight" else ""
        line = f"- [{prefix}{entry.type}] (from: {sources}, relevance: {score:.2f}): {content}"
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
    """Save synthesized Q&A as a new insight memory entry.

    Guards against memory amplification:
    - confidence=0.35 (well below fact=1.0 / claim=0.8)
    - embedding dedup: skip if >0.92 similar to existing entry
    - insights excluded from default search_memory results
    """
    if len(query) > 1000:
        query = query[:1000]
    content = f"Q: {query}\nA: {answer[:500]}"
    entry_id = make_entry_id("qa", query)

    if store.get(entry_id):
        return  # ID exact duplicate

    # Embedding-based dedup: skip near-duplicates
    if len(index) > 0:
        top_matches = index.search(content, k=1)
        if top_matches and top_matches[0][1] > 0.92:
            return  # semantically near-duplicate

    entry = MemoryEntry(
        id=entry_id,
        type="insight",
        content=content,
        source_papers=["synthesized_qa"],
        domain_tags=[],
        confidence=0.35,
    )
    store.add(entry)
    index.add(entry_id, content)

    try:
        store.save(MEMORY_DIR / "memory_store.json")
        index.save(MEMORY_DIR)
    except Exception:
        _log.warning("Failed to persist Q&A memory", exc_info=True)
