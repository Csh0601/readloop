"""Shared utility functions across ReadLoop subsystems."""
from __future__ import annotations

import hashlib
import re


def make_paper_id(name: str) -> str:
    """Stable slug from paper name. Primary key across all subsystems.

    Strips known suffixes, slugifies, caps at 80 chars.
    """
    for suffix in ["-逐页转图片(1)", "-逐页转图片", "逐页转图片"]:
        name = name.replace(suffix, "")
    name = name.strip()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", name.lower().strip())
    return s.strip("-")[:80] or "unnamed"


def safe_dirname(name: str) -> str:
    """Safe directory name from paper name (for filesystem)."""
    return re.sub(r'[\\/:*?"<>|]', '_', name[:80]).strip()


def make_entry_id(kind: str, *parts: str) -> str:
    """Deterministic ID for memory entries. SHA-256, 16 hex chars."""
    raw = ":".join([kind] + list(parts))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
