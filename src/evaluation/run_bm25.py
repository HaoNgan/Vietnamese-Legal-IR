"""Build and evaluate a reproducible BM25 run on locked Zalo validation data."""

from __future__ import annotations

import argparse
import ctypes
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "data/processed/benchmarks/zalo_2021"
REFERENCE = ROOT.parent / "references/vietnamese-legal-ir"

import src  # noqa: E402

# Import the project evaluator/metric definitions before extending src.__path__
# with the reference checkout, so this runner always uses the locked evaluator.
from src.evaluation.evaluate_runs import load_qrels, load_run  # noqa: E402
from src.evaluation.metrics import query_metrics  # noqa: E402

# The baseline implementation and Vietnamese preprocessing are pinned in this
# reference checkout. Do not modify the checkout from this project runner.
src.__path__ = [str(REFERENCE / "src"), *list(src.__path__)]
from src.retrieval.bm25_retrieval import BM25Retriever  # noqa: E402


DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
K1_GRID = (1.2, 1.5, 1.8)
B_GRID = (0.5, 0.75, 1.0)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    """Return a deterministic nearest-rank percentile (fraction in [0, 1])."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def peak_process_memory_bytes() -> int | None:
    """Read peak process RSS/working set without adding a runtime dependency."""
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        current_process = kernel32.GetCurrentProcess
        current_process.restype = ctypes.c_void_p
        get_memory_info = psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        get_memory_info.restype = ctypes.c_int
        ok = get_memory_info(current_process(), ctypes.byref(counters), counters.cb)
        return int(counters.PeakWorkingSetSize) if ok else None

    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def reference_revision() -> str:
    result = subprocess.run(
        [
            "git", "-C", str(REFERENCE), "-c",
            f"safe.directory={REFERENCE.as_posix()}", "rev-parse", "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def evaluate_rankings(
    qrels: dict[str, dict[str, int]],
    rankings: dict[str, list[str]],
) -> tuple[dict[str, float], list[dict]]:
    per_query = []
    totals: dict[str, float] = {}
    for qid, labels in qrels.items():
        values = query_metrics(rankings.get(qid, []), labels)
        per_query.append({"qid": qid, **values, "run_depth": len(rankings.get(qid, []))})
        for name, value in values.items():
            totals[name] = totals.get(name, 0.0) + value
    metrics = {name: value / len(qrels) for name, value in totals.items()}
    return metrics, per_query


def write_run(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["qid", "doc_id", "rank", "score"])
        writer.writeheader()
        writer.writerows(rows)


def run_configuration(
    retriever: BM25Retriever,
    queries: dict[str, str],
    qrels: dict[str, dict[str, int]],
    corpus_ids: set[str],
    top_k: int,
    k1: float,
    b: float,
    run_name: str,
    output_dir: Path,
) -> dict:
    # The index statistics/postings are independent of k1 and b. Reusing this
    # fitted index makes validation tuning avoid repeated corpus tokenization.
    retriever.k1, retriever.b = k1, b
    rows = []
    rankings: dict[str, list[str]] = {}
    latencies_ms = []
    for number, (qid, query) in enumerate(queries.items(), 1):
        started = time.perf_counter()
        results = retriever.search(query, top_k=top_k)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        ranked_ids = [str(item["doc_id"]) for item in results]
        rankings[qid] = ranked_ids
        rows.extend(
            {
                "qid": qid,
                "doc_id": str(item["doc_id"]),
                "rank": rank,
                "score": float(item["score"]),
            }
            for rank, item in enumerate(results, 1)
        )
        if number % 64 == 0 or number == len(queries):
            print(f"{run_name}: retrieved {number}/{len(queries)} validation queries")

    run_path = output_dir / "predictions" / f"{run_name}.csv"
    write_run(run_path, rows)
    rankings = load_run(run_path, corpus_ids)
    unknown_qids = set(rankings) - set(qrels)
    if unknown_qids:
        raise ValueError(f"Predictions contain qids absent from validation qrels: {sorted(unknown_qids)[:5]}")
    metrics, per_query = evaluate_rankings(qrels, rankings)
    per_query_path = output_dir / "per_query" / f"{run_name}.csv"
    per_query_path.parent.mkdir(parents=True, exist_ok=True)
    with per_query_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_query[0]))
        writer.writeheader()
        writer.writerows(per_query)
    return {
        "run_name": run_name,
        "k1": k1,
        "b": b,
        "queries": len(queries),
        "prediction_rows": len(rows),
        **metrics,
        "query_latency_ms_p50": round(percentile(latencies_ms, 0.50), 3),
        "query_latency_ms_p95": round(percentile(latencies_ms, 0.95), 3),
        "run_path": run_path,
        "run_sha256": sha256(run_path),
        "per_query_path": per_query_path,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=BENCHMARK / "corpus.jsonl")
    parser.add_argument("--queries", type=Path, default=BENCHMARK / "queries.jsonl")
    parser.add_argument("--qrels", type=Path, default=BENCHMARK / "qrels_validation.jsonl")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--k1-grid", type=float, nargs="+", default=list(K1_GRID))
    parser.add_argument("--b-grid", type=float, nargs="+", default=list(B_GRID))
    parser.add_argument(
        "--reuse-index", type=Path,
        help="Load an existing BM25 index after verifying its corpus document IDs.",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/bm25")
    args = parser.parse_args()
    if args.top_k < 50:
        parser.error("--top-k must be at least 50 to report Recall@50")
    if any(k1 <= 0 for k1 in args.k1_grid):
        parser.error("all --k1-grid values must be positive")
    if any(not 0 <= b <= 1 for b in args.b_grid):
        parser.error("all --b-grid values must be between 0 and 1")
    args.output_dir = args.output_dir.resolve()

    corpus_rows = read_jsonl(args.corpus)
    corpus: dict[str, str] = {}
    for row in corpus_rows:
        doc_id = str(row["doc_id"])
        if doc_id in corpus:
            raise ValueError(f"Duplicate corpus doc_id: {doc_id}")
        corpus[doc_id] = f"{row.get('title', '')} {row.get('text', '')}".strip()

    qrels = load_qrels(args.qrels)
    corpus_ids = set(corpus)
    missing_relevant_ids = sorted(
        {doc_id for labels in qrels.values() for doc_id, grade in labels.items() if grade > 0}
        - corpus_ids
    )
    if missing_relevant_ids:
        raise ValueError(
            f"Validation qrels reference {len(missing_relevant_ids)} missing corpus IDs: "
            f"{missing_relevant_ids[:5]}"
        )

    query_rows = read_jsonl(args.queries)
    query_map = {str(row["qid"]): str(row["query"]) for row in query_rows}
    if len(query_map) != len(query_rows):
        raise ValueError("Query IDs are not unique")
    missing_qids = set(qrels) - query_map.keys()
    if missing_qids:
        raise ValueError(f"Validation qids missing query text: {sorted(missing_qids)[:5]}")
    queries = {qid: query_map[qid] for qid in qrels}

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.reuse_index:
        index_path = args.reuse_index.resolve()
        print(f"Loading BM25 index: {index_path}")
        retriever = BM25Retriever.load(index_path)
        if retriever.num_docs != len(corpus) or set(map(str, retriever.doc_ids)) != corpus_ids:
            raise ValueError("Saved BM25 index document IDs do not match the locked corpus")
        fit_seconds = None
    else:
        print(f"Fitting BM25 once: {len(corpus):,} corpus documents")
        retriever = BM25Retriever(k1=DEFAULT_K1, b=DEFAULT_B)
        fit_started = time.perf_counter()
        retriever.fit(corpus)
        fit_seconds = time.perf_counter() - fit_started

    configurations = [(DEFAULT_K1, DEFAULT_B, "default_k1_1.5_b_0.75")]
    for k1 in args.k1_grid:
        for b in args.b_grid:
            if (k1, b) != (DEFAULT_K1, DEFAULT_B):
                configurations.append((k1, b, f"grid_k1_{k1:g}_b_{b:g}"))
    results = [
        run_configuration(retriever, queries, qrels, corpus_ids, args.top_k, k1, b, name, output_dir)
        for k1, b, name in configurations
    ]

    # Select only on the locked validation split. nDCG@10 is the predeclared
    # primary criterion; the remaining metrics break ties deterministically.
    best = max(
        results,
        key=lambda row: (
            row["ndcg@10"], row["map"], row["mrr"], row["recall@10"],
            row["recall@50"], -row["query_latency_ms_p95"],
        ),
    )
    if not args.reuse_index:
        index_path = output_dir / "bm25_index.pkl"
        retriever.k1, retriever.b = best["k1"], best["b"]
        retriever.save(index_path)
    index_path = index_path.resolve()

    comparison_fields = [
        "run_name", "k1", "b", "queries", "prediction_rows", "recall@10",
        "recall@50", "mrr", "map", "ndcg@10", "query_latency_ms_p50",
        "query_latency_ms_p95", "run_sha256",
    ]
    comparison_path = output_dir / "metrics_comparison.csv"
    with comparison_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=comparison_fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in comparison_fields} for row in results)

    run_script = Path(__file__).resolve()
    evaluator_script = ROOT / "src/evaluation/evaluate_runs.py"
    metrics_script = ROOT / "src/evaluation/metrics.py"
    benchmark_manifest = BENCHMARK / "manifest.json"
    config = {
        "benchmark": "Zalo AI Legal Text Retrieval 2021",
        "dataset_revision": "5fb3df4300b3a81455fe09af444ec159afa8d212",
        "split": "validation",
        "validation_queries": len(queries),
        "corpus_documents": len(corpus),
        "top_k": args.top_k,
        "selection": {
            "primary_metric": "nDCG@10",
            "tie_break_order": ["MAP", "MRR", "Recall@10", "Recall@50", "lower p95 latency"],
            "split_used_for_selection": "validation",
            "test_qrels_used": False,
        },
        "bm25": {
            "implementation": "Daijestic BM25Retriever, in-memory inverted postings",
            "tokenization": "Pinned reference preprocess: clean text, Underthesea word_tokenize, remove reference stopwords",
            "default": {"k1": DEFAULT_K1, "b": DEFAULT_B},
            "grid_k1": args.k1_grid,
            "grid_b": args.b_grid,
            "best_validation": {"k1": best["k1"], "b": best["b"], "run_name": best["run_name"]},
            "random_seed": None,
        },
        "reference_revision": reference_revision(),
        "software": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or None,
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "underthesea": package_version("underthesea"),
        },
        "timing": {
            "index_fit_seconds": round(fit_seconds, 3) if fit_seconds is not None else None,
            "latency_scope": "Per-query search call including preprocessing; excludes index fitting, loading, and output writing. First query is included.",
        },
        "index_source": {
            "mode": "loaded from saved index for reproducibility run" if args.reuse_index else "built in this run",
            "path": str(index_path),
            "sha256": sha256(index_path),
            "document_count_matches_corpus_ids": retriever.num_docs == len(corpus),
        },
        "resources": {
            "corpus_file_bytes": args.corpus.stat().st_size,
            "index_file_bytes": index_path.stat().st_size,
            "process_peak_working_set_bytes": peak_process_memory_bytes(),
            "memory_scope": (
                "Peak process RSS/working set across index fitting, tuning, and serialization; not an isolated index-size measurement."
                if not args.reuse_index else
                "Peak process RSS/working set across loading the saved index and validation retrieval; excludes the original index-build process and is not an isolated index-size measurement."
            ),
        },
        "artifacts": {
            "index": str(index_path),
            "index_sha256": sha256(index_path),
            "metrics_comparison": str(comparison_path),
            "predictions_dir": str(output_dir / "predictions"),
            "per_query_metrics_dir": str(output_dir / "per_query"),
            "runs": [
                {"name": row["run_name"], "path": str(row["run_path"]), "sha256": row["run_sha256"]}
                for row in results
            ],
        },
        "code_sha256": {
            "runner": sha256(run_script),
            "evaluator": sha256(evaluator_script),
            "metrics": sha256(metrics_script),
        },
        "input_sha256": {
            "corpus": sha256(args.corpus),
            "queries": sha256(args.queries),
            "qrels_validation": sha256(args.qrels),
            "benchmark_manifest": sha256(benchmark_manifest),
        },
    }
    config_path = output_dir / "run_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_lines = [
        "BM25 validation baseline and parameter sweep completed.",
        f"Dataset revision: {config['dataset_revision']}",
        f"Corpus documents: {len(corpus)}",
        f"Validation queries: {len(queries)}",
        f"Run depth: {args.top_k}",
        f"BM25 fit seconds: {fit_seconds:.3f}" if fit_seconds is not None else "BM25 index loaded from saved artifact",
        f"Reference revision: {config['reference_revision']}",
        f"Selected on validation by nDCG@10: {best['run_name']} (k1={best['k1']}, b={best['b']})",
        f"Index SHA-256: {config['artifacts']['index_sha256']}",
    ]
    for row in results:
        log_lines.append(
            f"{row['run_name']}: Recall@10={row['recall@10']:.6f}, "
            f"Recall@50={row['recall@50']:.6f}, MRR={row['mrr']:.6f}, "
            f"MAP={row['map']:.6f}, nDCG@10={row['ndcg@10']:.6f}, "
            f"latency_p50/p95_ms={row['query_latency_ms_p50']}/{row['query_latency_ms_p95']}"
        )
    (output_dir / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(f"Best validation parameters: k1={best['k1']}, b={best['b']}")
    print(f"Metric comparison: {comparison_path}")
    print(f"Saved BM25 index: {index_path}")
    print(f"Run config: {config_path}")
    print(f"Run log: {output_dir / 'run.log'}")


if __name__ == "__main__":
    main()
