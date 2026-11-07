"""Build/reuse BGE-M3 embeddings and evaluate exact dense retrieval on validation."""

from __future__ import annotations

import argparse
import atexit
import csv
import hashlib
import json
import math
import os
import platform
import time
import ctypes
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from src.data.loaders import read_jsonl
from src.evaluation.evaluate_runs import load_qrels, load_run
from src.evaluation.metrics import query_metrics
from src.retrieval.dense import DenseEncoder, encode_corpus_sharded, retrieve, shard_encoding_timing
from src.retrieval.faiss_index import FaissVectorIndex


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def peak_working_set_bytes() -> int | None:
    if os.name != "nt":
        try:
            import resource
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return int(value if platform.system() == "Darwin" else value * 1024)
        except ImportError:
            return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32, psapi = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("psapi", use_last_error=True)
    process = kernel32.GetCurrentProcess
    process.restype = ctypes.c_void_p
    get_info = psapi.GetProcessMemoryInfo
    get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    get_info.restype = ctypes.c_int
    return int(counters.PeakWorkingSetSize) if get_info(process(), ctypes.byref(counters), counters.cb) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/dense.yaml")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reuse-index", action="store_true")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--shard-size", type=int)
    parser.add_argument("--devices", nargs="+")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.batch_size is not None:
        config["batch_size"] = args.batch_size
    if args.shard_size is not None:
        config["shard_size"] = args.shard_size
    if args.devices is not None:
        config["devices"] = args.devices
    if int(config["top_k"]) < 50:
        raise ValueError("top_k must be at least 50 to report Recall@50")
    if int(config["batch_size"]) <= 0 or int(config["shard_size"]) <= 0:
        raise ValueError("batch_size and shard_size must be positive")
    for key in ("corpus", "queries", "qrels", "manifest"):
        config[key] = (ROOT / config[key]).resolve() if not Path(config[key]).is_absolute() else Path(config[key])
        if not config[key].is_file():
            raise FileNotFoundError(f"Required {key} file is missing: {config[key]}")
    baseline_metrics_path = (ROOT / config["baseline_metrics"]).resolve()
    if not baseline_metrics_path.is_file():
        raise FileNotFoundError(f"BM25 baseline metrics are missing: {baseline_metrics_path}")
    out = (args.output_dir or ROOT / config["output_dir"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    corpus = read_jsonl(config["corpus"])
    ids = [str(row["doc_id"]) for row in corpus]
    if len(ids) != len(set(ids)):
        raise ValueError("Corpus doc_id values must be unique")
    corpus_ids = set(ids)
    documents_by_id = {str(row["doc_id"]): row for row in corpus}
    qrels = load_qrels(config["qrels"])
    query_rows = read_jsonl(config["queries"])
    queries_all = {str(row["qid"]): str(row["query"]) for row in query_rows}
    if len(queries_all) != len(query_rows):
        raise ValueError("Query IDs must be unique")
    missing_qids = set(qrels) - queries_all.keys()
    if missing_qids:
        raise ValueError(f"Validation qids missing query text: {sorted(missing_qids)[:5]}")
    queries = {qid: queries_all[qid] for qid in qrels}
    if any(not text.strip() for text in queries.values()):
        raise ValueError("Validation contains empty query text")
    missing_docs = {doc for labels in qrels.values() for doc, grade in labels.items() if grade > 0} - corpus_ids
    if missing_docs:
        raise ValueError(f"Positive validation qrels reference absent corpus IDs: {sorted(missing_docs)[:5]}")

    import torch
    torch.manual_seed(int(config["seed"]))
    encoder = DenseEncoder(
        config["model_name"], config.get("model_revision"), config.get("device"), config.get("devices")
    )
    atexit.register(encoder.close)
    gpu_metadata = {"available": bool(torch.cuda.is_available()), "device": None,
                    "cuda_version": torch.version.cuda, "total_memory_bytes": None,
                    "peak_allocated_bytes": None}
    if gpu_metadata["available"]:
        gpu_properties = torch.cuda.get_device_properties(0)
        gpu_metadata["device"] = torch.cuda.get_device_name(0)
        gpu_metadata["total_memory_bytes"] = int(gpu_properties.total_memory)
        torch.cuda.reset_peak_memory_stats(0)
    index_path = out / "dense.faiss"
    build_seconds = 0.0
    index_build_seconds = 0.0
    shard_timing = None
    if args.reuse_index:
        if not index_path.is_file():
            raise FileNotFoundError(
                f"--reuse-index requested but no FAISS index exists at {index_path}; "
                "run without --reuse-index to build it from the saved embedding shards"
            )
        index = FaissVectorIndex.load(index_path)
        if index.document_ids != ids:
            raise ValueError("Saved FAISS ID mapping does not exactly match locked corpus order")
    else:
        build_start = time.perf_counter()
        vectors, mapped_ids = encode_corpus_sharded(
            encoder, corpus, out / "embedding_shards", int(config["batch_size"]), int(config["shard_size"])
        )
        if mapped_ids != ids or vectors.shape[0] != len(corpus):
            raise ValueError("Embedding rows do not map one-to-one to corpus documents")
        shard_timing = shard_encoding_timing(out / "embedding_shards", len(corpus), int(config["shard_size"]))
        index_build_start = time.perf_counter()
        index = FaissVectorIndex.build(vectors, ids)
        index.save(index_path)
        index_build_seconds = time.perf_counter() - index_build_start
        build_seconds = time.perf_counter() - build_start
    rows, latencies = retrieve(encoder, index, queries, int(config["top_k"]))
    if gpu_metadata["available"]:
        gpu_metadata["peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated(0))
    for row in rows:
        document = documents_by_id[row["doc_id"]]
        row["title"] = str(document.get("title", ""))
        row["snippet"] = str(document.get("text", ""))[:500]
    run_path = out / "predictions.csv"
    with run_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["qid", "doc_id", "rank", "score", "title", "snippet"])
        writer.writeheader()
        writer.writerows(rows)
    rankings = load_run(run_path, corpus_ids)
    if set(rankings) != set(queries):
        missing = set(queries) - set(rankings)
        if missing:
            # Empty query runs should be represented in query-level reports but are an explicit failure here.
            raise ValueError(f"Queries without retrieved results: {sorted(missing)[:5]}")
    per_query = [{"qid": qid, **query_metrics(rankings.get(qid, []), qrels[qid])} for qid in qrels]
    metrics = {name: sum(row[name] for row in per_query) / len(per_query) for name in query_metrics([], next(iter(qrels.values())))}
    with (out / "per_query_metrics.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_query[0]))
        writer.writeheader()
        writer.writerows(per_query)
    metric_path = out / "metrics.json"
    metric_path.write_text(json.dumps({"queries": len(qrels), "prediction_rows": len(rows), "metrics_macro_average": metrics}, indent=2) + "\n", encoding="utf-8")
    with baseline_metrics_path.open(encoding="utf-8-sig", newline="") as stream:
        baseline_rows = list(csv.DictReader(stream))
    baseline = next((row for row in baseline_rows if row["run_name"] == config["baseline_run_name"]), None)
    if baseline is None or int(baseline["queries"]) != len(qrels):
        raise ValueError("Configured BM25 run is absent or uses a different number of validation queries")
    comparison_path = out / "comparison_b0_b1.csv"
    comparison = [
        {"method": "B0 BM25", "split": config["split"], **{name: float(baseline[name]) for name in metrics},
         "latency_p50_ms": float(baseline["query_latency_ms_p50"]), "latency_p95_ms": float(baseline["query_latency_ms_p95"])},
        {"method": "B1 BGE-M3 + FAISS", "split": config["split"], **metrics,
         "latency_p50_ms": round(percentile(latencies, .50), 3), "latency_p95_ms": round(percentile(latencies, .95), 3)},
    ]
    with comparison_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    import importlib.metadata
    metadata = {
        "method": "B1 dense retrieval", "model": config["model_name"],
        "requested_model_revision": config.get("model_revision"),
        "resolved_model_revision": encoder.resolved_revision,
        "resolved_model_path": encoder.resolved_model_path, "split": config["split"], "seed": config["seed"],
        "corpus_documents": len(corpus), "validation_queries": len(queries), "top_k": config["top_k"],
        "embedding_dimension": index.dimension, "normalization": "L2", "similarity": "inner product = cosine",
        "index_type": "IndexFlatIP", "index_bytes": index_path.stat().st_size,
        "batch_size": int(config["batch_size"]), "shard_size": int(config["shard_size"]),
        "devices": config.get("devices") or [config.get("device") or "auto"],
        "mapping_bytes": index_path.with_suffix(index_path.suffix + ".json").stat().st_size,
        "index_and_mapping_bytes": index_path.stat().st_size + index_path.with_suffix(index_path.suffix + ".json").stat().st_size,
        "index_sha256": sha256(index_path), "mapping_sha256": sha256(index_path.with_suffix(index_path.suffix + ".json")),
        "build_seconds_this_invocation": round(build_seconds, 3),
        "faiss_index_build_and_save_seconds": round(index_build_seconds, 3),
        "corpus_shard_timing": shard_timing,
        "model_max_sequence_length": int(encoder.model.max_seq_length),
        "gpu": gpu_metadata,
        "latency_ms": {"p50": round(percentile(latencies, .5), 3), "p95": round(percentile(latencies, .95), 3),
                       "scope": "query embedding plus FAISS search; corpus encoding excluded"},
        "peak_working_set_bytes": peak_working_set_bytes(), "software": {"python": platform.python_version(), "platform": platform.platform(),
        "torch": importlib.metadata.version("torch"), "sentence_transformers": importlib.metadata.version("sentence-transformers"),
        "faiss": importlib.metadata.version("faiss-cpu")},
        "inputs_sha256": {key: sha256(config[key]) for key in ("corpus", "queries", "qrels", "manifest")},
        "baseline_metrics_sha256": sha256(baseline_metrics_path),
        "artifacts": {"index": str(index_path), "mapping": str(index_path.with_suffix(index_path.suffix + ".json")),
                      "predictions": str(run_path), "metrics": str(metric_path),
                      "per_query_metrics": str(out / "per_query_metrics.csv"),
                      "comparison": str(comparison_path)},
    }
    (out / "run_config.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": metrics, "latency_ms": metadata["latency_ms"], "index_bytes": metadata["index_bytes"], "build_seconds_this_invocation": build_seconds}, indent=2))


if __name__ == "__main__":
    main()
