"""Prepare a reproducible G0 subset from the upstream Daijestic data."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import pyarrow.ipc as ipc

try:
    csv.field_size_limit(2**31 - 1)
except OverflowError:
    csv.field_size_limit(100_000_000)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT.parent / "references" / "vietnamese-legal-ir"
OUTPUT = ROOT / "data" / "processed"
RAW_REPO = "tmnam20/BKAI-Legal-Retrieval"
RAW_REVISION = "276f9dce66055e033e0d7c6bf3e6e8d59e9e6d89"
EVAL_REPO = "YuITC/Vietnamese-Legal-Documents"
EVAL_REVISION = "a5195e351b08074529795283c77b4c9787c727f9"
EVAL_CACHE = Path.home() / ".cache" / "huggingface" / "datasets" / "YuITC___vietnamese-legal-documents"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_reference_queries(max_queries: int) -> tuple[dict[str, str], dict[str, list[str]], str]:
    """Read the cached YuITC Arrow split in the same train-then-test order."""
    queries: dict[str, str] = {}
    qrels: dict[str, list[str]] = {}
    arrow_path = EVAL_CACHE / "default" / "0.0.0" / EVAL_REVISION / "vietnamese-legal-documents-train.arrow"
    if arrow_path.is_file():
        with arrow_path.open("rb") as stream:
            table = ipc.open_stream(stream).read_all()
        required = {"question", "qid", "cid"}
        if not required.issubset(table.column_names):
            raise ValueError(f"Unexpected YuITC schema: {table.schema}")
        rows = table.select(sorted(required)).to_pylist()
    else:
        from datasets import load_dataset
        dataset = load_dataset(EVAL_REPO, revision=EVAL_REVISION)
        rows = dataset["train"]
        arrow_path = None
    for row in rows:
        qid = str(row["qid"])
        if qid in queries:
            raise ValueError(f"Duplicate YuITC qid; refusing to rewrite IDs: {qid}")
        query = str(row["question"] or "").strip()
        if not query:
            raise ValueError(f"Empty query text for YuITC qid={qid}")
        queries[qid] = query
        qrels[qid] = list(dict.fromkeys(str(cid) for cid in (row["cid"] or [])))
    selected = list(queries)[:max_queries]
    if len(selected) != max_queries:
        raise ValueError(f"Requested {max_queries} queries but YuITC train has {len(selected)}")
    return ({qid: queries[qid] for qid in selected},
            {qid: qrels[qid] for qid in selected}, EVAL_REVISION)


def reference_revision() -> str:
    result = subprocess.run(
        ["git", "-C", str(REFERENCE), "-c", f"safe.directory={REFERENCE.as_posix()}", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-docs", type=int, default=5000)
    parser.add_argument("--max-queries", type=int, default=500)
    parser.add_argument("--archive", type=Path, help="Path to authenticated BKAI archive.zip")
    args = parser.parse_args()
    if args.max_docs <= 0 or args.max_queries <= 0:
        parser.error("max-docs and max-queries must be positive")

    queries, qrels, eval_revision = load_reference_queries(args.max_queries)
    relevant = {str(doc) for ids in qrels.values() for doc in ids}

    archive_path = args.archive
    if archive_path is None:
        from huggingface_hub import hf_hub_download
        try:
            archive_path = Path(hf_hub_download(
                repo_id=RAW_REPO, filename="archive.zip", repo_type="dataset",
                revision=RAW_REVISION,
            ))
        except Exception as exc:
            raise RuntimeError(
                "Cannot resolve BKAI archive.zip. Supply --archive with the verified source file."
            ) from exc
    if not archive_path.is_file() or archive_path.stat().st_size == 0:
        raise RuntimeError(f"BKAI archive is missing or empty: {archive_path}")

    corpus: dict[str, str] = {}
    seen_ids: set[str] = set()
    with ZipFile(archive_path) as archive:
        if "corpus.csv" not in archive.namelist():
            raise ValueError("BKAI archive has no corpus.csv")
        with archive.open("corpus.csv") as stream:
            reader = csv.DictReader((line.decode("utf-8-sig") for line in stream))
            if not {"cid", "text"}.issubset(reader.fieldnames or []):
                raise ValueError(f"Unexpected corpus.csv schema: {reader.fieldnames}")
            for row in reader:
                cid = str(row["cid"])
                if cid in seen_ids:
                    raise ValueError(f"Duplicate corpus CID: {cid}")
                seen_ids.add(cid)
                if cid in relevant:
                    corpus[cid] = row["text"] or ""

    missing = relevant - corpus.keys()
    if missing:
        raise ValueError(f"{len(missing)} qrel document IDs are absent from BKAI corpus")
    if len(corpus) > args.max_docs:
        raise ValueError(
            f"{len(corpus)} unique relevant documents exceed max-docs={args.max_docs}; "
            "increase the limit rather than dropping qrel labels"
        )

    # Second deterministic source-order pass fills the remaining slots, while
    # retaining all qrel-relevant documents first.
    with ZipFile(archive_path) as archive, archive.open("corpus.csv") as stream:
        reader = csv.DictReader((line.decode("utf-8-sig") for line in stream))
        for row in reader:
            cid = str(row["cid"])
            if cid not in corpus:
                corpus[cid] = row["text"] or ""
            if len(corpus) == args.max_docs:
                break
    if len(corpus) != args.max_docs:
        raise ValueError(f"Requested {args.max_docs} docs, source yielded {len(corpus)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    outputs = {"corpus.json": corpus, "queries.json": queries, "qrels.json": qrels}
    for filename, data in outputs.items():
        temp = OUTPUT / (filename + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temp.replace(OUTPUT / filename)

    manifest = {
        "purpose": "G0 diagnostic subset; not the independent Zalo benchmark",
        "raw_dataset": RAW_REPO,
        "raw_dataset_revision": RAW_REVISION,
        "raw_archive_sha256": sha256(archive_path),
        "evaluation_dataset": EVAL_REPO,
        "evaluation_revision": eval_revision,
        "reference_repository": "Daijestic/vietnamese-legal-ir",
        "reference_revision": reference_revision(),
        "selection": {
            "queries": "first N rows in the pinned YuITC train Arrow split order",
            "corpus": "all qrel-relevant documents, then source-order documents to max_docs",
            "max_docs": args.max_docs,
            "max_queries": args.max_queries,
        },
        "counts": {
            "source_corpus_documents": len(seen_ids),
            "documents": len(corpus), "queries": len(queries),
            "qrels": sum(len(ids) for ids in qrels.values()),
            "queries_with_relevant_docs": sum(bool(qrels[qid]) for qid in queries),
            "unique_relevant_documents": len(relevant),
            "relevant_documents_missing": 0,
        },
        "files_sha256": {
            name: hashlib.sha256((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()).hexdigest()
            for name, data in outputs.items()
        },
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print(f"Manifest: {OUTPUT / 'manifest.json'}")


if __name__ == "__main__":
    try:
        main()
    except (BadZipFile, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Data preparation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
