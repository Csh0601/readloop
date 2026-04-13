"""记忆存储 -- 从 analysis.md 提取 + 持久化"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..client import LLMClient
from ..config import MEMORY_DIR
from .models import MemoryStore, MemoryEntry
from .embeddings import EmbeddingIndex
from .prompts import EXTRACT_MEMORIES


def _make_id(content: str, paper: str) -> str:
    """Deterministic ID from content + paper."""
    h = hashlib.md5(f"{paper}:{content}".encode()).hexdigest()[:12]
    return h


def extract_memories_from_analysis(
    analysis_text: str,
    paper_name: str,
    client: LLMClient,
) -> list[MemoryEntry]:
    """Extract memory entries from an analysis.md using LLM."""
    if len(analysis_text) > 40000:
        analysis_text = analysis_text[:40000]

    prompt = EXTRACT_MEMORIES.format(
        analysis_text=analysis_text,
        paper_name=paper_name,
    )
    data = client.chat_json(prompt, max_tokens=4000)

    entries = []
    for fact in data.get("facts", []):
        entries.append(MemoryEntry(
            id=_make_id(fact["content"], paper_name),
            type="fact",
            content=fact["content"],
            source_papers=[paper_name],
            domain_tags=fact.get("tags", []),
            confidence=1.0,
        ))
    for claim in data.get("claims", []):
        entries.append(MemoryEntry(
            id=_make_id(claim["content"], paper_name),
            type="claim",
            content=claim["content"],
            source_papers=[paper_name],
            domain_tags=claim.get("tags", []),
            confidence=claim.get("confidence", 0.8),
        ))
    return entries


def build_memory_from_analyses(
    output_dir: Path,
    client: LLMClient,
) -> tuple[MemoryStore, EmbeddingIndex]:
    """Build full memory store + embedding index from all analyses."""
    store_path = MEMORY_DIR / "memory_store.json"
    store = MemoryStore()
    index = EmbeddingIndex()

    batch_entries: list[tuple[str, str]] = []

    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir() or paper_dir.name.startswith("00_"):
            continue

        analysis_path = paper_dir / "analysis.md"
        if not analysis_path.exists():
            continue

        print(f"  extracting memories: {paper_dir.name[:50]}...")
        analysis = analysis_path.read_text(encoding="utf-8")

        try:
            entries = extract_memories_from_analysis(analysis, paper_dir.name, client)
        except Exception as e:
            print(f"    failed: {e}")
            continue

        for entry in entries:
            store.add(entry)
            batch_entries.append((entry.id, entry.content))

    # Build embeddings in batch (much faster)
    if batch_entries:
        print(f"  building embeddings for {len(batch_entries)} entries...")
        index.add_batch(batch_entries)

    # Save
    store.save(store_path)
    index.save(MEMORY_DIR)

    return store, index
