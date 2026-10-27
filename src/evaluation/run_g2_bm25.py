"""Build a BM25 run on the locked Zalo validation split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "data/processed/benchmarks/zalo_2021"
REFERENCE = ROOT.parent / "references/vietnamese-legal-ir"

import src  # noqa: E402

# Resolve the pinned reference implementation and its preprocessing modules.
src.__path__ = [str(REFERENCE / "src"), *list(src.__path__)]
from src.retrieval.bm25_retrieval import BM25Retriever  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision() -> str:
    result = subprocess.run(
        ["git", "-C", str(REFERENCE), "-c", f"safe.directory={REFERENCE.as_posix()}", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=BENCHMARK / "corpus.jsonl")
    parser.add_argument("--queries", type=Path, default=BENCHMARK / "queries.jsonl")
    parser.add_argument("--qrels", type=Path, default=BENCHMARK / "qrels_validation.jsonl")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--k1", type=float, default=1.5)
    parser.add_argument("--b", type=float, default=0.75)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/g2_bm25")
    args = parser.parse_args()
    if args.top_k < 50:
        parser.error("--top-k must be at least 50 to report Recall@50")

    corpus_rows = read_jsonl(args.corpus)
    corpus: dict[str, str] = {}
    for row in corpus_rows:
        doc_id = str(row["doc_id"])
        if doc_id in corpus:
            raise ValueError(f"Duplicate corpus doc_id: {doc_id}")
        corpus[doc_id] = f"{row.get('title', '')} {row.get('text', '')}".strip()

    validation_qids = {str(row["qid"]) for row in read_jsonl(args.qrels)}
    query_rows = [row for row in read_jsonl(args.queries) if str(row["qid"]) in validation_qids]
    queries = {str(row["qid"]): str(row["query"]) for row in query_rows}
    missing_qids = validation_qids - queries.keys()
    if missing_qids:
        raise ValueError(f"Validation qids missing query text: {sorted(missing_qids)[:5]}")
    if len(queries) != len(validation_qids):
        raise ValueError("Validation query IDs are not unique")

    print(f"Fitting BM25: {len(corpus):,} corpus documents")
    retriever = BM25Retriever(k1=args.k1, b=args.b)
    retriever.fit(corpus)

    rows = []
    for number, (qid, query) in enumerate(queries.items(), 1):
        results = retriever.search(query, top_k=args.top_k)
        rows.extend({
            "qid": qid,
            "doc_id": str(item["doc_id"]),
            "rank": rank,
            "score": float(item["score"]),
        } for rank, item in enumerate(results, 1))
        if number % 32 == 0 or number == len(queries):
            print(f"Retrieved {number}/{len(queries)} validation queries")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_path = args.output_dir / "bm25_validation_run.csv"
    with run_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["qid", "doc_id", "rank", "score"])
        writer.writeheader()
        writer.writerows(rows)

    config = {
        "benchmark": "Zalo AI Legal Text Retrieval 2021",
        "split": "validation",
        "queries": len(queries),
        "corpus_documents": len(corpus),
        "top_k": args.top_k,
        "bm25": {"k1": args.k1, "b": args.b},
        "tokenization": "Pinned Daijestic vietnamese-legal-ir preprocess",
        "reference_revision": git_revision(),
        "input_sha256": {
            "corpus": sha256(args.corpus),
            "queries": sha256(args.queries),
            "qrels_validation": sha256(args.qrels),
        },
        "run_sha256": sha256(run_path),
        "prediction_rows": len(rows),
    }
    config_path = args.output_dir / "run_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_lines = [
        "BM25 validation run completed.",
        f"Corpus documents: {len(corpus)}",
        f"Validation queries: {len(queries)}",
        f"Top K: {args.top_k}",
        f"BM25 k1: {args.k1}",
        f"BM25 b: {args.b}",
        f"Reference revision: {config['reference_revision']}",
        f"Prediction rows: {len(rows)}",
        f"Run SHA-256: {config['run_sha256']}",
    ]
    (args.output_dir / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Ranked run: {run_path}")
    print(f"Run config: {config_path}")
    print(f"Run log: {args.output_dir / 'run.log'}")


if __name__ == "__main__":
    main()
