"""Dense embedding and retrieval with resumable corpus encoding."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import time

import numpy as np


class DenseEncoder:
    def __init__(
        self,
        model_name: str,
        revision: str | None = None,
        device: str | None = None,
        devices: list[str] | None = None,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is required for dense retrieval") from exc
        if devices and device:
            raise ValueError("choose either a single device or multiple devices, not both")
        if devices and len(devices) < 2:
            raise ValueError("multi-process encoding needs at least two devices")
        kwargs = {"device": "cpu" if devices else device} if (device or devices) else {}
        if revision:
            kwargs["revision"] = revision
        self.model = SentenceTransformer(model_name, **kwargs)
        self.model_name = model_name
        self.revision = revision
        self.devices = list(devices) if devices else None
        self.pool = self.model.start_multi_process_pool(target_devices=self.devices) if self.devices else None
        self.resolved_model_path = str(getattr(self.model, "_model_card_vars", {}).get("base_model", model_name))
        # Sentence Transformers resolves Hub checkpoints into immutable snapshot directories.
        for module in self.model._modules.values():
            path = getattr(module, "auto_model", None)
            path = getattr(getattr(path, "config", None), "_name_or_path", None)
            if path:
                self.resolved_model_path = str(path)
                break
        parts = Path(self.resolved_model_path).parts
        self.resolved_revision = next((parts[i + 1] for i, part in enumerate(parts[:-1])
                                       if part == "snapshots" and len(parts[i + 1]) == 40), revision)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not texts:
            return np.empty((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        vectors = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True, pool=self.pool,
            chunk_size=2 * batch_size if self.pool else None,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or not np.isfinite(vectors).all():
            raise ValueError("model returned malformed or non-finite embeddings")
        return vectors

    def close(self) -> None:
        """Stop optional Sentence Transformers worker processes cleanly."""
        if self.pool is not None:
            self.model.stop_multi_process_pool(self.pool)
            self.pool = None


def encode_corpus_sharded(
    encoder: DenseEncoder,
    documents: list[dict],
    output_dir: str | Path,
    batch_size: int = 32,
    shard_size: int = 1024,
) -> tuple[np.ndarray, list[str]]:
    """Write one atomic NPZ shard at a time and reuse completed valid shards."""
    if batch_size <= 0 or shard_size <= 0:
        raise ValueError("batch_size and shard_size must be positive")
    ids = [str(row["doc_id"]) for row in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("corpus document IDs must be unique")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_vectors = []
    shard_count = math.ceil(len(documents) / shard_size)
    for shard_num, start in enumerate(range(0, len(documents), shard_size)):
        part = documents[start:start + shard_size]
        path = output_dir / f"shard_{shard_num:05d}.npz"
        expected_ids = np.asarray(ids[start:start + shard_size], dtype=str)
        texts = [f"{row.get('title', '')}\n{row.get('text', '')}".strip() or "[EMPTY LEGAL DOCUMENT]"
                 for row in part]
        source_hash = hashlib.sha256("\0".join(
            f"{doc_id}\0{text}" for doc_id, text in zip(expected_ids.tolist(), texts)
        ).encode("utf-8")).hexdigest()
        vectors = None
        encoding_seconds = None
        if path.is_file():
            try:
                with np.load(path, allow_pickle=False) as stored:
                    if np.array_equal(stored["ids"], expected_ids) and str(stored["source_sha256"].item()) == source_hash:
                        vectors = stored["vectors"].astype(np.float32, copy=False)
                        if "encoding_seconds" in stored.files:
                            encoding_seconds = float(stored["encoding_seconds"].item())
                        if (vectors.ndim != 2 or vectors.shape[0] != len(part) or not np.isfinite(vectors).all()
                                or (len(part) and not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3))):
                            vectors = None
            except (OSError, ValueError, KeyError):
                vectors = None
        if vectors is None:
            encode_start = time.perf_counter()
            vectors = encoder.encode(texts, batch_size=batch_size)
            encoding_seconds = time.perf_counter() - encode_start
            if vectors.shape[0] != len(part) or (len(part) and not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3)):
                raise ValueError("encoder output rows or normalization do not match corpus shard")
            temporary = path.with_suffix(".tmp.npz")
            np.savez(temporary, ids=expected_ids, source_sha256=np.asarray(source_hash), vectors=vectors,
                     encoding_seconds=np.asarray(encoding_seconds, dtype=np.float64))
            temporary.replace(path)
        all_vectors.append(vectors)
        print(f"Corpus embeddings: {min(start + shard_size, len(documents))}/{len(documents)} documents "
              f"({shard_num + 1}/{shard_count} shards)", flush=True)
    dimension = all_vectors[0].shape[1] if all_vectors else encoder.model.get_sentence_embedding_dimension()
    return (np.concatenate(all_vectors, axis=0) if all_vectors else np.empty((0, dimension), np.float32)), ids


def shard_encoding_timing(output_dir: str | Path, document_count: int, shard_size: int) -> dict:
    """Summarize persisted per-shard encoder time; old shards without timing are marked incomplete."""
    if document_count < 0 or shard_size <= 0:
        raise ValueError("document_count must be non-negative and shard_size positive")
    output_dir = Path(output_dir)
    shard_count = math.ceil(document_count / shard_size)
    total_seconds = 0.0
    complete = True
    for shard_num in range(shard_count):
        path = output_dir / f"shard_{shard_num:05d}.npz"
        try:
            with np.load(path, allow_pickle=False) as stored:
                value = float(stored["encoding_seconds"].item())
            if not math.isfinite(value) or value < 0:
                complete = False
            else:
                total_seconds += value
        except (OSError, ValueError, KeyError):
            complete = False
    return {"complete": complete, "shards": shard_count,
            "encoder_seconds": round(total_seconds, 3) if complete else None}


def retrieve(encoder: DenseEncoder, index, queries: dict[str, str], top_k: int) -> tuple[list[dict], list[float]]:
    """Return qid/doc_id ranked rows and per-query search latency in ms."""
    import time

    rows, latencies = [], []
    for qid, query in queries.items():
        start = time.perf_counter()
        if not str(query).strip():
            latencies.append(0.0)
            continue
        qvec = encoder.encode([str(query)])
        results = index.search(qvec, top_k)[0]
        latencies.append((time.perf_counter() - start) * 1000)
        rows.extend({"qid": str(qid), "doc_id": cid, "rank": rank, "score": score}
                    for rank, (cid, score) in enumerate(results, 1))
    return rows, latencies
