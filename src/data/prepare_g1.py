"""Validate pinned Zalo/YuITC data and create a locked Zalo benchmark bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import pyarrow.ipc as ipc

from src.data.loaders import write_jsonl
from src.data.preprocess import normalize_text, query_fingerprint

ROOT = Path(__file__).resolve().parents[2]
ZALO_REPO = "minhnguyent546/zalo-ai-legal-text-retrieval-2021"
ZALO_REVISION = "5fb3df4300b3a81455fe09af444ec159afa8d212"
YUITC_REPO = "YuITC/Vietnamese-Legal-Documents"
YUITC_REVISION = "a5195e351b08074529795283c77b4c9787c727f9"
BKAI_REPO = "tmnam20/BKAI-Legal-Retrieval"
BKAI_REVISION = "276f9dce66055e033e0d7c6bf3e6e8d59e9e6d89"
ZALO_CACHE = Path.home() / ".cache/huggingface/datasets/minhnguyent546___zalo-ai-legal-text-retrieval-2021"
YUITC_CACHE = Path.home() / ".cache/huggingface/datasets/YuITC___vietnamese-legal-documents/default/0.0.0"
BKAI_CACHE = (Path.home() / ".cache/huggingface/hub/datasets--tmnam20--BKAI-Legal-Retrieval"
              / "snapshots" / BKAI_REVISION / "archive.zip")
DEFAULT_OUTPUT = ROOT / "data/processed/benchmarks/zalo_2021"
DEFAULT_REPORT = ROOT / "outputs/reports/g1_data_lock"
DEFAULT_CONFIG = ROOT / "configs/g1_data_lock.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locked_source_paths() -> dict[str, Path]:
    snapshot = ZALO_CACHE / "corpus/0.0.0" / ZALO_REVISION
    query_snapshot = ZALO_CACHE / "queries/0.0.0" / ZALO_REVISION
    qrel_snapshot = ZALO_CACHE / "qrels/0.0.0" / ZALO_REVISION
    yuitc_snapshot = YUITC_CACHE / YUITC_REVISION
    return {
        "corpus": snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "queries": query_snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "qrels_train": qrel_snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "qrels_test": qrel_snapshot / "zalo-ai-legal-text-retrieval-2021-test.arrow",
        "yuitc_train_arrow": yuitc_snapshot / "vietnamese-legal-documents-train.arrow",
        "yuitc_test_arrow": yuitc_snapshot / "vietnamese-legal-documents-test.arrow",
        "bkai_archive": BKAI_CACHE,
    }


def verify_lock(output_dir: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No G1 lock manifest found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for filename, expected in manifest["processed_sha256"].items():
        path = output_dir / filename
        if not path.is_file() or sha256_file(path) != expected:
            mismatches.append(f"processed/{filename}")
    config_hash = hashlib.sha256(DEFAULT_CONFIG.read_bytes()).hexdigest()
    if config_hash != manifest["config_sha256"]:
        mismatches.append("configs/g1_data_lock.json")
    for name, path in locked_source_paths().items():
        if not path.is_file() or sha256_file(path) != manifest["source_sha256"].get(name):
            mismatches.append(f"source/{name}")
    if mismatches:
        raise ValueError(f"G1 lock verification failed: {mismatches}")
    print(f"G1 lock verified: {manifest_path}")
    print(f"Processed artifacts verified: {len(manifest['processed_sha256'])}")
    print(f"Pinned source artifacts verified: {len(manifest['source_sha256'])}")


def read_arrow(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Pinned Arrow file not found: {path}")
    with path.open("rb") as stream:
        return ipc.open_stream(stream).read_all().to_pylist()


def quantiles(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "p25": None, "median": None, "mean": None,
                "p75": None, "p90": None, "p95": None, "p99": None, "max": None}
    ordered = sorted(values)
    def percentile(p: float) -> int:
        return ordered[round((len(ordered) - 1) * p)]
    return {
        "min": ordered[0], "p25": percentile(.25), "median": percentile(.5),
        "mean": round(statistics.fmean(ordered), 4), "p75": percentile(.75),
        "p90": percentile(.90), "p95": percentile(.95), "p99": percentile(.99),
        "max": ordered[-1],
    }


def read_zalo_source() -> tuple[dict[str, list[dict]], dict[str, Path]]:
    snapshot = ZALO_CACHE / "corpus/0.0.0" / ZALO_REVISION
    query_snapshot = ZALO_CACHE / "queries/0.0.0" / ZALO_REVISION
    qrel_snapshot = ZALO_CACHE / "qrels/0.0.0" / ZALO_REVISION
    paths = {
        "corpus": snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "queries": query_snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "qrels_train": qrel_snapshot / "zalo-ai-legal-text-retrieval-2021-train.arrow",
        "qrels_test": qrel_snapshot / "zalo-ai-legal-text-retrieval-2021-test.arrow",
    }
    rows = {key: read_arrow(path) for key, path in paths.items()}
    expected = {
        "corpus": {"id", "title", "text"},
        "queries": {"query_id", "question"},
        "qrels_train": {"corpus_id", "query_id", "score"},
        "qrels_test": {"corpus_id", "query_id", "score"},
    }
    for key, required in expected.items():
        actual = set(rows[key][0]) if rows[key] else set()
        if not required.issubset(actual):
            raise ValueError(f"Unexpected Zalo {key} schema: fields={sorted(actual)}")
    return rows, paths


def split_qids(train_qids: list[str], validation_fraction: float, seed: str) -> tuple[list[str], list[str]]:
    if not 0 < validation_fraction < 1:
        raise ValueError("validation-fraction must be between 0 and 1")
    n_validation = round(len(train_qids) * validation_fraction)
    ordered = sorted(train_qids, key=lambda qid: hashlib.sha256(f"{seed}\0{qid}".encode()).hexdigest())
    validation = ordered[:n_validation]
    validation_set = set(validation)
    train = [qid for qid in train_qids if qid not in validation_set]
    return train, validation


def analyze_yuitc() -> dict:
    paths = {split: YUITC_CACHE / YUITC_REVISION / f"vietnamese-legal-documents-{split}.arrow"
             for split in ("train", "test")}
    splits = {name: read_arrow(path) for name, path in paths.items()}
    query_fingerprints: dict[str, set[str]] = {}
    split_reports = {}
    all_relevant: set[str] = set()
    for split, rows in splits.items():
        if rows and not {"question", "context_list", "qid", "cid"}.issubset(rows[0]):
            raise ValueError(f"Unexpected YuITC schema for {split}: {sorted(rows[0])}")
        qids = [str(row["qid"]) for row in rows]
        if len(qids) != len(set(qids)):
            raise ValueError(f"Duplicate YuITC qid in official {split} split")
        queries = [normalize_text(row["question"]) for row in rows]
        query_fingerprints[split] = {query_fingerprint(q) for q in queries}
        qrel_counts = [len(row["cid"] or []) for row in rows]
        all_relevant.update(str(cid) for row in rows for cid in (row["cid"] or []))
        split_reports[split] = {
            "query_rows": len(rows),
            "unique_qids": len(set(qids)),
            "qrel_rows": sum(qrel_counts),
            "unique_relevant_cids": len({str(cid) for row in rows for cid in (row["cid"] or [])}),
            "queries_with_empty_text": sum(not q for q in queries),
            "queries_with_no_qrels": sum(count == 0 for count in qrel_counts),
            "duplicate_normalized_query_rows": len(queries) - len(set(map(query_fingerprint, queries))),
            "query_char_lengths": quantiles([len(q) for q in queries]),
            "query_word_lengths": quantiles([len(q.split()) for q in queries]),
            "qrel_documents_per_query": quantiles(qrel_counts),
            "source_sha256": sha256_file(paths[split]),
        }
    cross_split_query_texts = query_fingerprints["train"] & query_fingerprints["test"]
    split_reports["official_train_test_exact_query_text_overlap_groups"] = len(cross_split_query_texts)

    archive_ids: set[str] = set()
    word_lengths: list[int] = []
    empty_docs = 0
    duplicate_text_rows = 0
    seen_text_hashes: set[str] = set()
    if not BKAI_CACHE.is_file():
        raise FileNotFoundError(f"Pinned BKAI archive not found: {BKAI_CACHE}")
    csv.field_size_limit(2**31 - 1)
    with ZipFile(BKAI_CACHE) as archive:
        with archive.open("corpus.csv") as stream:
            reader = csv.DictReader(line.decode("utf-8-sig") for line in stream)
            if not {"cid", "text"}.issubset(reader.fieldnames or []):
                raise ValueError(f"Unexpected BKAI corpus schema: {reader.fieldnames}")
            missing = set(all_relevant)
            for row in reader:
                cid = str(row["cid"])
                if cid in archive_ids:
                    raise ValueError(f"Duplicate BKAI CID: {cid}")
                archive_ids.add(cid)
                missing.discard(cid)
                text = normalize_text(row.get("text", ""))
                word_lengths.append(len(text.split()))
                empty_docs += not bool(text)
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if digest in seen_text_hashes:
                    duplicate_text_rows += 1
                seen_text_hashes.add(digest)
    if missing:
        raise ValueError(f"{len(missing)} YuITC relevant CIDs are absent from pinned BKAI corpus")
    split_reports["corpus"] = {
        "source_dataset": BKAI_REPO,
        "source_revision": BKAI_REVISION,
        "documents": len(archive_ids),
        "unique_cids": len(archive_ids),
        "empty_text_documents": empty_docs,
        "duplicate_normalized_text_rows": duplicate_text_rows,
        "word_lengths": quantiles(word_lengths),
        "sha256": sha256_file(BKAI_CACHE),
    }
    return {
        "dataset": YUITC_REPO,
        "revision": YUITC_REVISION,
        "role": "Secondary analysis only; not the locked primary benchmark.",
        "official_splits": split_reports,
        "query_text_exact_overlap_is_leakage_risk": bool(cross_split_query_texts),
        "cross_split_overlap_note": (
            "Exact normalized query text occurs in both official splits. Preserve official files, "
            "but do not present this split as leakage-free independent confirmation without a protocol." 
            if cross_split_query_texts else "No exact normalized query text overlap across official splits."
        ),
    }


def main() -> None:
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    if config.get("dataset_repository") != ZALO_REPO or config.get("dataset_revision") != ZALO_REVISION:
        raise ValueError("G1 config source does not match the pinned Zalo source in this adapter")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--validation-fraction", type=float, default=config["validation_fraction"])
    parser.add_argument("--seed", default=config["split_seed"])
    parser.add_argument("--force", action="store_true", help="Replace only this G1 output directory")
    parser.add_argument("--verify", action="store_true", help="Verify locked files and hashes without rewriting them")
    args = parser.parse_args()

    if args.verify:
        verify_lock(args.output_dir)
        return
    existing_manifest = args.output_dir / "manifest.json"
    if existing_manifest.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite locked output: {existing_manifest}; pass --force deliberately")
    zalo, zalo_paths = read_zalo_source()
    corpus_rows, query_rows = zalo["corpus"], zalo["queries"]
    corpus_ids = [str(row["id"]) for row in corpus_rows]
    query_ids = [str(row["query_id"]) for row in query_rows]
    if len(corpus_ids) != len(set(corpus_ids)):
        raise ValueError("Duplicate Zalo corpus ID")
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Duplicate Zalo query ID")
    if any(not normalize_text(row["question"]) for row in query_rows):
        raise ValueError("Empty Zalo query text")
    normalized_queries = {str(row["query_id"]): query_fingerprint(row["question"]) for row in query_rows}
    if len(normalized_queries.values()) != len(set(normalized_queries.values())):
        raise ValueError("Duplicate normalized Zalo query text; group before splitting")
    corpus_id_set, query_id_set = set(corpus_ids), set(query_ids)

    qrels_by_split: dict[str, list[dict]] = {}
    split_qid_sets: dict[str, set[str]] = {}
    for split in ("train", "test"):
        rows = zalo[f"qrels_{split}"]
        pairs: set[tuple[str, str]] = set()
        normalized = []
        for row in rows:
            qid, doc_id = str(row["query_id"]), str(row["corpus_id"])
            if qid not in query_id_set:
                raise ValueError(f"Zalo {split} qrel references unknown qid={qid}")
            if doc_id not in corpus_id_set:
                raise ValueError(f"Zalo {split} qrel references unknown corpus ID={doc_id}")
            if (qid, doc_id) in pairs:
                raise ValueError(f"Duplicate Zalo qrel pair: {qid}/{doc_id}")
            pairs.add((qid, doc_id))
            relevance = int(row["score"])
            if relevance <= 0:
                raise ValueError(f"Non-positive relevance in official Zalo qrels: {qid}/{doc_id}")
            normalized.append({"qid": qid, "doc_id": doc_id, "relevance": relevance})
        qrels_by_split[split] = normalized
        split_qid_sets[split] = {row["qid"] for row in normalized}
        if any(not any(qrel["relevance"] > 0 for qrel in normalized if qrel["qid"] == qid)
               for qid in split_qid_sets[split]):
            raise ValueError(f"Zalo {split} contains a query with no positive qrel")

    train_test_qid_overlap = split_qid_sets["train"] & split_qid_sets["test"]
    if train_test_qid_overlap:
        raise ValueError(f"Official Zalo train/test qid overlap: {sorted(train_test_qid_overlap)[:5]}")
    uncovered_queries = query_id_set - split_qid_sets["train"] - split_qid_sets["test"]
    unknown_qids = (split_qid_sets["train"] | split_qid_sets["test"]) - query_id_set
    if uncovered_queries or unknown_qids:
        raise ValueError(f"Zalo query/qrel split mismatch: uncovered={len(uncovered_queries)}, unknown={len(unknown_qids)}")

    official_train_qids = [str(row["query_id"]) for row in zalo["queries"]
                           if str(row["query_id"]) in split_qid_sets["train"]]
    train_qids, validation_qids = split_qids(official_train_qids, args.validation_fraction, args.seed)
    test_qids = [str(row["query_id"]) for row in zalo["queries"]
                 if str(row["query_id"]) in split_qid_sets["test"]]
    split_sets = {"train": set(train_qids), "validation": set(validation_qids), "test": set(test_qids)}
    if split_sets["train"] & split_sets["validation"] or split_sets["train"] & split_sets["test"] or split_sets["validation"] & split_sets["test"]:
        raise ValueError("Derived Zalo split qids overlap")
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if {normalized_queries[qid] for qid in split_sets[left]} & {normalized_queries[qid] for qid in split_sets[right]}:
            raise ValueError(f"Exact normalized Zalo query-text leakage across {left}/{right}")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    normalized_corpus = []
    for row in corpus_rows:
        normalized_corpus.append({"doc_id": str(row["id"]), "title": normalize_text(row["title"]),
                                  "text": normalize_text(row["text"])})
    normalized_queries = [{"qid": str(row["query_id"]), "query": normalize_text(row["question"])}
                          for row in query_rows]
    write_jsonl(output / "corpus.jsonl", normalized_corpus)
    write_jsonl(output / "queries.jsonl", normalized_queries)
    qrels_for_locked_splits = {
        split: [row for row in qrels_by_split["train"] if row["qid"] in split_sets[split]]
        for split in ("train", "validation")
    }
    qrels_for_locked_splits["test"] = qrels_by_split["test"]
    for split, rows in qrels_for_locked_splits.items():
        write_jsonl(output / f"qrels_{split}.jsonl", rows)
    splits = {split: sorted(qids) for split, qids in split_sets.items()}
    (output / "splits.json").write_text(json.dumps(splits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zalo_doc_lengths = [len(row["text"].split()) for row in normalized_corpus]
    zalo_doc_hashes = [hashlib.sha256(row["text"].encode("utf-8")).hexdigest() for row in normalized_corpus]
    normalized_query_by_id = {row["qid"]: row["query"] for row in normalized_queries}
    qrels_per_qid = Counter(row["qid"] for rows in qrels_for_locked_splits.values() for row in rows)
    all_qrels = qrels_by_split["train"] + qrels_by_split["test"]
    report = {
        "schema": {
            "zalo_source": {
                "corpus": ["id", "title", "text"],
                "queries": ["query_id", "question"],
                "qrels": ["query_id", "corpus_id", "score"],
            },
            "yuitc_source": {
                "query_qrels_rows": ["question", "context_list", "qid", "cid"],
                "related_bkai_corpus": ["cid", "text"],
            },
            "canonical_processed": {
                "corpus": ["doc_id", "title", "text"],
                "queries": ["qid", "query"],
                "qrels": ["qid", "doc_id", "relevance"],
            },
        },
        "primary_benchmark": {
            "name": "Zalo AI Legal Text Retrieval 2021",
            "repository": ZALO_REPO,
            "revision": ZALO_REVISION,
            "corpus_documents": len(normalized_corpus),
            "queries": len(normalized_queries),
            "official_qrels_rows": {"train": len(qrels_by_split["train"]), "test": len(qrels_by_split["test"])},
            "locked_queries": {split: len(ids) for split, ids in splits.items()},
            "locked_qrels_rows": {split: len(rows) for split, rows in qrels_for_locked_splits.items()},
            "qrel_relevance_levels": dict(sorted(Counter(row["relevance"] for row in all_qrels).items())),
            "integrity": {
                "duplicate_corpus_ids": len(normalized_corpus) - len({row["doc_id"] for row in normalized_corpus}),
                "duplicate_query_ids": len(normalized_queries) - len({row["qid"] for row in normalized_queries}),
                "duplicate_normalized_query_text_rows": 0,
                "duplicate_qrel_pairs": 0,
                "qrel_cids_missing_from_corpus": 0,
                "query_ids_without_qrels": 0,
                "official_train_test_qid_overlap": len(train_test_qid_overlap),
                "cross_split_exact_query_text_overlap": 0,
                "empty_text_documents_preserved": sum(not row["text"] for row in normalized_corpus),
                "duplicate_normalized_document_text_rows_preserved": len(dalo := zalo_doc_hashes) - len(set(dalo)),
            },
            "document_word_lengths": quantiles(zalo_doc_lengths),
            "query_word_lengths": quantiles([len(row["query"].split()) for row in normalized_queries]),
            "query_character_lengths": quantiles([len(row["query"]) for row in normalized_queries]),
            "relevant_documents_per_query": quantiles(list(qrels_per_qid.values())),
        },
        "secondary_dataset": analyze_yuitc(),
        "methodology": {
            "normalization": "Unicode NFC and whitespace collapse for text fields; IDs and relevance labels preserved.",
            "official_split": "Zalo qrels train/test qids retained; deterministic validation is carved only from official train qids.",
            "validation_fraction": args.validation_fraction,
            "split_seed": args.seed,
            "test_use": "Do not use test judgments for model selection or tuning. The cached mirror exposes test qrels; their presence does not authorize tuning on them.",
            "shared_corpus": "The same corpus is available to all query splits, as standard in retrieval; relevance labels remain split-specific.",
        },
    }
    source_hashes = {key: sha256_file(path) for key, path in zalo_paths.items()}
    source_hashes["yuitc_train_arrow"] = report["secondary_dataset"]["official_splits"]["train"]["source_sha256"]
    source_hashes["yuitc_test_arrow"] = report["secondary_dataset"]["official_splits"]["test"]["source_sha256"]
    source_hashes["bkai_archive"] = sha256_file(BKAI_CACHE)
    file_hashes = {path.name: sha256_file(path) for path in sorted(output.iterdir())
                   if path.is_file() and path.name != "manifest.json"}
    manifest = {
        "schema_version": 1,
        "benchmark": ZALO_REPO,
        "revision": ZALO_REVISION,
        "secondary_dataset": YUITC_REPO,
        "secondary_revision": YUITC_REVISION,
        "related_corpus": BKAI_REPO,
        "related_corpus_revision": BKAI_REVISION,
        "source_sha256": source_hashes,
        "processed_sha256": file_hashes,
        "config_sha256": hashlib.sha256(DEFAULT_CONFIG.read_bytes()).hexdigest(),
        "canonical_schema": report["schema"]["canonical_processed"],
        "counts": report["primary_benchmark"],
        "split_method": "Sort official Zalo train qids by SHA-256(seed + NUL + qid), assign first round(n*validation_fraction) to validation; retain official test qids.",
        "split_seed": args.seed,
        "validation_fraction": args.validation_fraction,
        "metric_protocol": {
            "recall@10": "relevant retrieved in top 10 / all positive qrels for qid",
            "recall@50": "relevant retrieved in top 50 / all positive qrels for qid",
            "mrr": "reciprocal rank of first relevant result within submitted run depth",
            "map": "average precision over submitted run depth, divided by all positive qrels for qid",
            "ndcg@10": "binary/graded gain 2^relevance-1, normalized by ideal top 10",
            "aggregation": "macro mean over every qid in selected qrels split; no qid silently dropped",
        },
        "test_policy": "Test qrels are stored unchanged. No test retrieval run or tuning is performed in G1.",
    }
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.report_dir / "dataset_report.md").write_text(render_report(report), encoding="utf-8")
    print(json.dumps(report["primary_benchmark"], ensure_ascii=False, indent=2))
    print(f"YUITC train/test exact normalized query text overlap groups: {report['secondary_dataset']['official_splits']['official_train_test_exact_query_text_overlap_groups']}")
    print(f"Processed benchmark: {output}")
    print(f"Dataset report: {args.report_dir / 'dataset_report.md'}")


def render_report(report: dict) -> str:
    p = report["primary_benchmark"]
    y = report["secondary_dataset"]
    integrity = p["integrity"]
    lines = [
        "# Dataset report and G1 data lock", "",
        "## Primary benchmark: Zalo AI Legal Text Retrieval 2021", "",
        f"Source: `{p['repository']}` at revision `{p['revision']}`.", "",
        "## Source and processed schemas", "",
        "Source fields: Zalo corpus `id/title/text`; queries `query_id/question`; qrels `query_id/corpus_id/score`. "
        "YuITC rows use `question/context_list/qid/cid`; the linked corpus is BKAI `cid/text`.", "",
        "Canonical JSONL fields: corpus `doc_id/title/text`; queries `qid/query`; qrels `qid/doc_id/relevance`. "
        "IDs and relevance values are preserved; text uses NFC and collapsed whitespace.", "",
        f"Corpus: {p['corpus_documents']:,} documents; queries: {p['queries']:,}; official qrel rows: "
        f"train {p['official_qrels_rows']['train']:,}, test {p['official_qrels_rows']['test']:,}.", "",
        "| Split | Queries | Qrel rows | Purpose |", "|---|---:|---:|---|",
        f"| Train | {p['locked_queries']['train']:,} | {p['locked_qrels_rows']['train']:,} | Development/training |",
        f"| Validation | {p['locked_queries']['validation']:,} | {p['locked_qrels_rows']['validation']:,} | Parameter/model selection |",
        f"| Test | {p['locked_queries']['test']:,} | {p['locked_qrels_rows']['test']:,} | Final evaluation only |", "",
        "## Data checks", "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in integrity.items())
    lines.extend(["", "## Length distributions", "", "Word counts use whitespace tokenization for descriptive statistics only.", "",
                  "| Field | Min | P25 | Median | Mean | P75 | P90 | P95 | P99 | Max |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for label, values in (("Zalo document words", p["document_word_lengths"]),
                          ("Zalo query words", p["query_word_lengths"]),
                          ("Zalo query characters", p["query_character_lengths"]),
                          ("Relevant docs/query", p["relevant_documents_per_query"])):
        lines.append("| " + label + " | " + " | ".join(str(values[key]) for key in
                     ("min", "p25", "median", "mean", "p75", "p90", "p95", "p99", "max")) + " |")
    lines.extend(["", "## YuITC secondary analysis", "",
                  f"Source: `{y['dataset']}` at revision `{y['revision']}`; corpus is pinned BKAI.", ""])
    for split in ("train", "test"):
        d = y["official_splits"][split]
        lines.append(f"- {split}: {d['query_rows']:,} query/qrel records, {d['qrel_rows']:,} qrel rows, "
                     f"{d['unique_relevant_cids']:,} unique relevant CIDs; median query length "
                     f"{d['query_word_lengths']['median']} words; median {d['qrel_documents_per_query']['median']} relevant document/query.")
    c = y["official_splits"]["corpus"]
    lines.extend([f"- BKAI corpus used to resolve YuITC CIDs: {c['documents']:,} documents; "
                  f"median {c['word_lengths']['median']} words/document; all positive qrel CIDs resolve.",
                  f"- Exact normalized query-text groups overlapping YuITC official train/test: "
                  f"{y['official_splits']['official_train_test_exact_query_text_overlap_groups']:,}.",
                  f"- Interpretation: {y['cross_split_overlap_note']}", "",
                  "| YuITC/BKAI text field | Min | P25 | Median | Mean | P75 | P90 | P95 | P99 | Max |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for label, values in (("YuITC train query words", y["official_splits"]["train"]["query_word_lengths"]),
                          ("YuITC test query words", y["official_splits"]["test"]["query_word_lengths"]),
                          ("BKAI corpus words", c["word_lengths"])):
        lines.append("| " + label + " | " + " | ".join(str(values[key]) for key in
                     ("min", "p25", "median", "mean", "p75", "p90", "p95", "p99", "max")) + " |")
    lines.extend(["",
                  "## Lock decisions and limitations", "",
                  "Zalo is the primary benchmark because the project guide identifies it as the main benchmark and its train/test query texts are disjoint in the pinned mirror. "
                  "Validation is a deterministic 10% query-level split carved only from official train; official test remains unchanged. "
                  "The corpus is shared across splits, as expected in retrieval; qrels are not shared. No retrieval model was run for G1.", "",
                  "Zalo has empty-text and duplicate-text documents. They are preserved in the locked corpus; reports disclose them. "
                  "Any later filtering must be a separately versioned experiment, never a silent change to this benchmark.", "",
                  "Metrics are macro-averaged over all qids in the selected qrels split. MRR and MAP use the submitted run depth, which must be reported. "
                  "Recall@10/50 and nDCG@10 use the fixed cutoffs. The test qrels are present in the local mirror and must not be used for selection or tuning.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"G1 data preparation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
