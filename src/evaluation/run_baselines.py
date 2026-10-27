"""Run the reference Boolean, TF-IDF and BM25 methods with strict evaluation."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT.parent / "references" / "vietnamese-legal-ir"
import src  # noqa: E402

# This project intentionally imports the retrieval implementation from the
# pinned reference checkout. Extend the current src package path so its
# absolute ``src.*`` imports resolve to that checkout, not empty local folders.
src.__path__ = [str(REFERENCE / "src"), *list(src.__path__)]

from src.indexing.inverted_index import InvertedIndex  # noqa: E402
from src.retrieval.boolean_retrieval import BooleanRetriever  # noqa: E402
from src.retrieval.tfidf_retrieval import TfidfRetriever  # noqa: E402
from src.retrieval.bm25_retrieval import BM25Retriever  # noqa: E402


def reference_revision() -> str:
    result = subprocess.run(
        ["git", "-C", str(REFERENCE), "-c", f"safe.directory={REFERENCE.as_posix()}", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def load(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metrics(ranked: list[str], relevant: set[str]) -> dict[str, float]:
    hits = [1 if doc_id in relevant else 0 for doc_id in ranked]
    recall = sum(hits) / len(relevant) if relevant else 0.0
    precision_sum = 0.0
    found = 0
    for rank, hit in enumerate(hits, 1):
        if hit:
            found += 1
            precision_sum += found / rank
    ap = precision_sum / len(relevant) if relevant else 0.0
    dcg = sum(hit / __import__("math").log2(rank + 1) for rank, hit in enumerate(hits, 1))
    # The ideal ranking uses the requested cutoff even when a retriever
    # returns fewer than k documents (matching Daijestic's ndcg_at_k).
    ideal_n = min(len(relevant), 10)
    idcg = sum(1 / __import__("math").log2(rank + 1) for rank in range(1, ideal_n + 1))
    return {"recall_at_10": recall, "map": ap, "ndcg_at_10": dcg / idcg if idcg else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/processed/corpus.json")
    parser.add_argument("--queries", type=Path, default=ROOT / "data/processed/queries.json")
    parser.add_argument("--qrels", type=Path, default=ROOT / "data/processed/qrels.json")
    parser.add_argument("--max-queries", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()
    corpus = {str(k): str(v) for k, v in load(args.corpus).items()}
    queries = load(args.queries)
    qrels = load(args.qrels)
    if not corpus:
        raise ValueError("Empty corpus")
    selected = []
    missing_labels = set()
    selected_source = list(queries.items())[:args.max_queries]
    for qid, query in selected_source:
        if str(qid) not in qrels:
            raise ValueError(f"Query {qid} has no qrels; refusing to skip it")
        rel = {str(x) for x in qrels[str(qid)]}
        if not rel:
            raise ValueError(f"Query {qid} has an empty qrel set; refusing to skip it")
        missing_labels.update(rel - corpus.keys())
        selected.append((str(qid), str(query), rel))
    if missing_labels:
        raise ValueError(f"qrels reference {len(missing_labels)} IDs missing from corpus")
    if len(selected) != args.max_queries:
        raise ValueError(f"Requested {args.max_queries} queries; only {len(selected)} available")

    index = InvertedIndex()
    index.build(corpus)
    retrievers = {
        "boolean": BooleanRetriever(index),
        "tfidf": TfidfRetriever(),
        "bm25": BM25Retriever(),
    }
    for method, retriever in retrievers.items():
        if method != "boolean":
            retriever.fit(corpus)

    rows = []
    prediction_rows = []
    top5_rows = []
    example_qids = {qid for qid, _, _ in selected[:10]}
    for method, retriever in retrievers.items():
        totals = {"recall_at_10": 0.0, "map": 0.0, "ndcg_at_10": 0.0}
        for qid, query, relevant in selected:
            results = retriever.search(query, top_k=max(args.top_k, 10))
            ranked = [str(row.get("doc_id", row.get("cid"))) for row in results]
            score_by_id = {str(row.get("doc_id", row.get("cid"))): float(row["score"]) for row in results}
            for key, value in metrics(ranked[:10], relevant).items():
                totals[key] += value
            for rank, doc_id in enumerate(ranked[:args.top_k], 1):
                text = corpus[doc_id]
                prediction_rows.append({
                    "method": method, "qid": qid, "query": query, "rank": rank,
                    "doc_id": doc_id, "score": score_by_id[doc_id], "relevant": doc_id in relevant,
                    "snippet": " ".join(text.split())[:300],
                })
                if qid in example_qids and rank <= 5:
                    top5_rows.append(prediction_rows[-1])
        rows.append({"method": method, "num_queries": len(selected), **{k: v / len(selected) for k, v in totals.items()}})

    report = args.output_dir / "reports" / "baseline_g0"
    predictions = args.output_dir / "predictions" / "baseline_g0"
    report.mkdir(parents=True, exist_ok=True)
    predictions.mkdir(parents=True, exist_ok=True)
    with (report / "evaluation_report.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    def write_csv(path: Path, data: list[dict]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)
    write_csv(predictions / "top_results.csv", prediction_rows)
    write_csv(predictions / "top5_examples.csv", top5_rows)
    config = {
        "reference_revision": reference_revision(),
        "corpus_sha256": file_sha256(args.corpus),
        "queries_sha256": file_sha256(args.queries),
        "qrels_sha256": file_sha256(args.qrels),
        "max_queries": args.max_queries,
        "top_k": args.top_k,
        "methods": list(retrievers),
        "evaluated_query_ids": [qid for qid, _, _ in selected],
        "prediction_count": len(prediction_rows),
    }
    (report / "run_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log_lines = [
        f"Reference revision: {config['reference_revision']}",
        f"Corpus documents: {len(corpus)}",
        f"Queries evaluated per method: {len(selected)}",
        f"Predictions written: {len(prediction_rows)}",
        "Metrics:",
        *[json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows],
    ]
    (report / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"Evaluated queries per method: {len(selected)}")
    print(f"Reports: {report}")


if __name__ == "__main__":
    main()
