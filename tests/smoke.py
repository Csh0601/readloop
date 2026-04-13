"""Minimal consistency checks after v2.2 refactor.

Usage: python -m tests.smoke
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import OUTPUT_DIR, MEMORY_DIR, GRAPH_DIR
from src.knowledge.models import KnowledgeGraph

OUTPUT = OUTPUT_DIR
MEMORY = MEMORY_DIR
GRAPH = GRAPH_DIR


def test_memory_index_sync():
    """All memory entries have corresponding embeddings."""
    from src.memory.models import MemoryStore
    from src.memory.embeddings import EmbeddingIndex

    store = MemoryStore.load(MEMORY / "memory_store.json")
    index = EmbeddingIndex.load(MEMORY)
    assert len(store.entries) == len(index), (
        f"Store has {len(store.entries)} entries but index has {len(index)}"
    )
    # Verify vector matrix matches ID list
    if index.vectors is not None:
        assert index.vectors.shape[0] == len(index.ids), (
            f"Vector matrix has {index.vectors.shape[0]} rows but "
            f"{len(index.ids)} IDs"
        )


def test_paper_id_consistency():
    """All source_papers in memory can be mapped to paper dirs."""
    from src.utils import make_paper_id
    from src.memory.models import MemoryStore

    store = MemoryStore.load(MEMORY / "memory_store.json")
    paper_ids = {
        make_paper_id(d.name)
        for d in OUTPUT.iterdir()
        if d.is_dir() and not d.name.startswith("00_")
    }

    mismatches = []
    for entry in store.entries.values():
        for src in entry.source_papers:
            if src == "synthesized_qa":
                continue
            pid = make_paper_id(src)
            if pid not in paper_ids and src not in paper_ids:
                mismatches.append(f"  entry {entry.id}: unknown paper '{src}' (pid={pid})")

    assert not mismatches, (
        f"{len(mismatches)} paper ID mismatches:\n" + "\n".join(mismatches[:10])
    )


def test_graph_no_dangling_edges():
    """All edge endpoints exist as nodes."""
    graph = KnowledgeGraph.load(GRAPH / "graph.json")
    dangling = []
    for edge in graph.edges:
        if edge.source not in graph.nodes:
            dangling.append(f"  dangling source: {edge.source}")
        if edge.target not in graph.nodes:
            dangling.append(f"  dangling target: {edge.target}")

    assert not dangling, (
        f"{len(dangling)} dangling edge endpoints:\n" + "\n".join(dangling[:10])
    )


def test_no_self_loops():
    """No edge has same source and target."""
    graph = KnowledgeGraph.load(GRAPH / "graph.json")
    loops = [e for e in graph.edges if e.source == e.target]
    assert not loops, f"{len(loops)} self-loop edges found"


if __name__ == "__main__":
    tests = [
        (name, func)
        for name, func in globals().items()
        if name.startswith("test_") and callable(func)
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            print(f"  PASS: {name}")
            passed += 1
        except FileNotFoundError as e:
            print(f"  SKIP: {name} (data not found: {e})")
        except AssertionError as e:
            print(f"  FAIL: {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
