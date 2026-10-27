"""Evaluate a ranked run against locked qrels; this module does not retrieve."""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from src.data.loaders import read_jsonl
from src.evaluation.metrics import query_metrics


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    for row in read_jsonl(path):
        qid, doc_id = str(row["qid"]), str(row["doc_id"])
        if doc_id in qrels[qid]:
            raise ValueError(f"Duplicate qrel pair: qid={qid}, doc_id={doc_id}")
        relevance = int(row["relevance"])
        if relevance < 0:
            raise ValueError(f"Negative qrel relevance for qid={qid}, doc_id={doc_id}")
        qrels[qid][doc_id] = relevance
    if not qrels:
        raise ValueError("Qrels file is empty")
    empty = [qid for qid, labels in qrels.items() if not any(value > 0 for value in labels.values())]
    if empty:
        raise ValueError(f"Queries with no positive qrel labels: {empty[:5]}")
    return dict(qrels)


def load_run(path: Path, corpus_ids: set[str]) -> dict[str, list[str]]:
    runs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    seen_ranks: set[tuple[str, int]] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"qid", "doc_id", "rank"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Run CSV must contain columns {sorted(required)}")
        for row in reader:
            qid, doc_id = str(row["qid"]), str(row["doc_id"])
            try:
                rank = int(row["rank"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid rank for qid={qid}, doc_id={doc_id}") from exc
            if rank <= 0:
                raise ValueError(f"Rank must be positive: qid={qid}, rank={rank}")
            if doc_id not in corpus_ids:
                raise ValueError(f"Run contains document ID absent from corpus: {doc_id}")
            pair = (qid, doc_id)
            if pair in seen_pairs:
                raise ValueError(f"Duplicate run document: qid={qid}, doc_id={doc_id}")
            if (qid, rank) in seen_ranks:
                raise ValueError(f"Duplicate run rank: qid={qid}, rank={rank}")
            seen_pairs.add(pair)
            seen_ranks.add((qid, rank))
            if row.get("score", ""):
                try:
                    score = float(row["score"])
                except ValueError as exc:
                    raise ValueError(f"Invalid score for qid={qid}, rank={rank}") from exc
                if not math.isfinite(score):
                    raise ValueError(f"Non-finite score for qid={qid}, rank={rank}")
            runs[qid].append((rank, doc_id))
    result = {}
    for qid, items in runs.items():
        items.sort()
        ranks = [rank for rank, _ in items]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"Run ranks for qid={qid} must be contiguous from 1; got {ranks[:10]}")
        result[qid] = [doc for _, doc in items]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qrels", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path, help="CSV with qid,doc_id,rank[,score]")
    parser.add_argument("--corpus", required=True, type=Path, help="JSONL with doc_id and text")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    qrels = load_qrels(args.qrels)
    corpus_rows = read_jsonl(args.corpus)
    corpus_ids = [str(row["doc_id"]) for row in corpus_rows]
    if len(corpus_ids) != len(set(corpus_ids)):
        raise ValueError("Corpus contains duplicate doc_id values")
    corpus_id_set = set(corpus_ids)
    missing = sorted({doc for labels in qrels.values() for doc, grade in labels.items() if grade > 0} - corpus_id_set)
    if missing:
        raise ValueError(f"Positive qrels reference {len(missing)} IDs absent from corpus; examples={missing[:5]}")
    run = load_run(args.run, corpus_id_set)
    unknown_qids = set(run) - set(qrels)
    if unknown_qids:
        raise ValueError(f"Run contains qids absent from qrels: {sorted(unknown_qids)[:5]}")

    per_query = []
    totals = {name: 0.0 for name in ("recall@10", "recall@50", "mrr", "map", "ndcg@10")}
    for qid in qrels:
        values = query_metrics(run.get(qid, []), qrels[qid])
        per_query.append({"qid": qid, **values, "run_depth": len(run.get(qid, []))})
        for name, value in values.items():
            totals[name] += value
    metrics = {name: value / len(qrels) for name, value in totals.items()}
    max_depths = sorted({row["run_depth"] for row in per_query})
    report = {
        "queries": len(qrels),
        "queries_with_run_rows": len(run),
        "queries_without_results_scored_as_empty": len(qrels) - len(run),
        "run_depth_values": max_depths,
        "map_and_mrr_interpretation": "Computed over the submitted ranked list; run depth is reported per query.",
        "metrics_macro_average": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_query_path = args.output.with_name(args.output.stem + "_per_query.csv")
    with per_query_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(per_query[0]))
        writer.writeheader()
        writer.writerows(per_query)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {args.output}")
    print(f"Per-query: {per_query_path}")


if __name__ == "__main__":
    main()
