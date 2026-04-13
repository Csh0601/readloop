"""记忆系统数据模型"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class MemoryEntry:
    id: str
    type: str                   # fact | claim | insight
    content: str                # the knowledge statement
    source_papers: list[str]    # which papers this comes from
    domain_tags: list[str] = field(default_factory=list)
    confidence: float = 1.0     # 0-1
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEntry:
        return cls(**d)


@dataclass
class MemoryStore:
    entries: dict[str, MemoryEntry] = field(default_factory=dict)
    version: int = 1

    def add(self, entry: MemoryEntry) -> None:
        self.entries[entry.id] = entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        return self.entries.get(entry_id)

    def get_by_type(self, entry_type: str) -> list[MemoryEntry]:
        return [e for e in self.entries.values() if e.type == entry_type]

    def get_by_paper(self, paper_name: str) -> list[MemoryEntry]:
        return [
            e for e in self.entries.values()
            if paper_name in e.source_papers
        ]

    def search_by_tag(self, tag: str) -> list[MemoryEntry]:
        tag_lower = tag.lower()
        return [
            e for e in self.entries.values()
            if any(tag_lower in t.lower() for t in e.domain_tags)
        ]

    def stats(self) -> dict:
        type_counts = {}
        for e in self.entries.values():
            type_counts[e.type] = type_counts.get(e.type, 0) + 1
        all_papers = set()
        for e in self.entries.values():
            all_papers.update(e.source_papers)
        return {
            "total_entries": len(self.entries),
            "type_counts": type_counts,
            "papers_covered": len(all_papers),
        }

    # --- Serialization ---

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self.version,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> MemoryStore:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        store = cls(version=data.get("version", 1))
        for k, v in data.get("entries", {}).items():
            store.entries[k] = MemoryEntry.from_dict(v)
        return store
