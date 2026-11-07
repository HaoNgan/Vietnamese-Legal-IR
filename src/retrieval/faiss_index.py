"""FAISS persistence and stable document-ID mapping for dense retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class FaissVectorIndex:
    """Exact cosine search using normalized float32 vectors and IndexFlatIP."""

    def __init__(self, index, document_ids: list[str], dimension: int):
        self.index = index
        self.document_ids = list(document_ids)
        self.dimension = int(dimension)
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("document IDs must be unique")
        if self.index.ntotal != len(self.document_ids):
            raise ValueError("FAISS vector count does not match document ID mapping")
        if self.index.d != self.dimension:
            raise ValueError("FAISS dimension does not match metadata")

    @classmethod
    def build(cls, vectors: np.ndarray, document_ids: list[str]) -> "FaissVectorIndex":
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS is required; install faiss-cpu") from exc
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(document_ids) or vectors.shape[1] == 0:
            raise ValueError("vectors must be a non-empty 2D matrix aligned with document IDs")
        if not np.isfinite(vectors).all():
            raise ValueError("vectors contain non-finite values")
        norms = np.linalg.norm(vectors, axis=1)
        if np.any(norms == 0) or not np.allclose(norms, 1.0, atol=1e-3):
            raise ValueError("vectors must be L2-normalized and non-zero")
        if len(document_ids) != len(set(map(str, document_ids))):
            raise ValueError("document IDs must be unique")
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(np.ascontiguousarray(vectors))
        return cls(index, list(map(str, document_ids)), vectors.shape[1])

    def search(self, query_vectors: np.ndarray, top_k: int) -> list[list[tuple[str, float]]]:
        query_vectors = np.asarray(query_vectors, dtype=np.float32)
        if query_vectors.ndim == 1:
            query_vectors = query_vectors.reshape(1, -1)
        if query_vectors.ndim != 2 or query_vectors.shape[1] != self.dimension:
            raise ValueError("query vectors have the wrong shape/dimension")
        if not np.isfinite(query_vectors).all():
            raise ValueError("query vectors contain non-finite values")
        if np.any(np.linalg.norm(query_vectors, axis=1) == 0):
            raise ValueError("query vectors must be non-zero")
        query_vectors = np.ascontiguousarray(query_vectors)
        k = min(max(0, int(top_k)), len(self.document_ids))
        if k == 0:
            return [[] for _ in range(len(query_vectors))]
        faiss_scores, faiss_ids = self.index.search(query_vectors, k)
        results = []
        for scores, ids in zip(faiss_scores, faiss_ids):
            rows = [(self.document_ids[int(i)], float(score)) for score, i in zip(scores, ids) if i >= 0]
            rows.sort(key=lambda row: (-row[1], row[0]))
            results.append(rows)
        return results

    def save(self, path: str | Path) -> tuple[Path, Path]:
        import faiss

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = path.with_suffix(path.suffix + ".json")
        faiss.write_index(self.index, str(path))
        metadata_path.write_text(json.dumps({
            "format": "faiss.IndexFlatIP",
            "similarity": "cosine (L2-normalized vectors)",
            "dimension": self.dimension,
            "document_ids": self.document_ids,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path, metadata_path

    @classmethod
    def load(cls, path: str | Path) -> "FaissVectorIndex":
        import faiss

        path = Path(path)
        metadata_path = path.with_suffix(path.suffix + ".json")
        if not path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"FAISS index or mapping is missing: {path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("format") != "faiss.IndexFlatIP":
            raise ValueError("unsupported FAISS index format")
        index = faiss.read_index(str(path))
        return cls(index, metadata["document_ids"], metadata["dimension"])
