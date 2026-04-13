"""本地 Embedding 封装 -- sentence-transformers, 无 API 成本"""
from __future__ import annotations

import numpy as np
from pathlib import Path

_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"  # 22MB, 384 dims, fast on CPU


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts, returns (N, 384) float32 array"""
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def embed_single(text: str) -> np.ndarray:
    """Embed a single text, returns (384,) float32 array"""
    return embed_texts([text])[0]


def cosine_similarity(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and corpus.

    Args:
        query_vec: (D,) normalized vector
        corpus_vecs: (N, D) normalized vectors

    Returns:
        (N,) similarity scores
    """
    return corpus_vecs @ query_vec


def top_k_similar(
    query_vec: np.ndarray,
    corpus_vecs: np.ndarray,
    k: int = 20,
) -> list[tuple[int, float]]:
    """Return top-k (index, score) pairs sorted by similarity descending."""
    scores = cosine_similarity(query_vec, corpus_vecs)
    top_indices = np.argsort(scores)[::-1][:k]
    return [(int(idx), float(scores[idx])) for idx in top_indices]


class EmbeddingIndex:
    """Manages an embedding index with save/load to numpy file."""

    def __init__(self):
        self.ids: list[str] = []
        self.vectors: np.ndarray | None = None

    def add(self, entry_id: str, text: str) -> None:
        vec = embed_single(text)
        self.ids.append(entry_id)
        if self.vectors is None:
            self.vectors = vec.reshape(1, -1)
        else:
            self.vectors = np.vstack([self.vectors, vec.reshape(1, -1)])

    def add_batch(self, entries: list[tuple[str, str]]) -> None:
        """Add multiple (id, text) pairs at once (faster)."""
        if not entries:
            return
        ids, texts = zip(*entries)
        vecs = embed_texts(list(texts))
        self.ids.extend(ids)
        if self.vectors is None:
            self.vectors = vecs
        else:
            self.vectors = np.vstack([self.vectors, vecs])

    def search(self, query: str, k: int = 20) -> list[tuple[str, float]]:
        """Search for top-k similar entries. Returns [(id, score), ...]."""
        if self.vectors is None or len(self.ids) == 0:
            return []
        query_vec = embed_single(query)
        results = top_k_similar(query_vec, self.vectors, k=k)
        return [(self.ids[idx], score) for idx, score in results]

    def save(self, dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        if self.vectors is not None:
            np.save(dir_path / "embeddings.npy", self.vectors)
        ids_path = dir_path / "embedding_ids.json"
        import json
        ids_path.write_text(json.dumps(self.ids, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, dir_path: Path) -> EmbeddingIndex:
        index = cls()
        npy_path = dir_path / "embeddings.npy"
        ids_path = dir_path / "embedding_ids.json"
        if npy_path.exists() and ids_path.exists():
            index.vectors = np.load(npy_path)
            import json
            index.ids = json.loads(ids_path.read_text(encoding="utf-8"))
        return index

    def __len__(self) -> int:
        return len(self.ids)
