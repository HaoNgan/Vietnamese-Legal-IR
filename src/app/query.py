"""Print real Top-K results for Boolean, TF-IDF and BM25."""
import argparse
import csv
import hashlib
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import src  # noqa: E402
src.__path__ = [str(ROOT.parent / "references" / "vietnamese-legal-ir" / "src"), *list(src.__path__)]
from src.indexing.inverted_index import InvertedIndex  # noqa: E402
from src.retrieval.boolean_retrieval import BooleanRetriever  # noqa: E402
from src.retrieval.tfidf_retrieval import TfidfRetriever  # noqa: E402
from src.retrieval.bm25_retrieval import BM25Retriever  # noqa: E402


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_revision() -> str:
    import subprocess
    reference = ROOT.parent / "references" / "vietnamese-legal-ir"
    result = subprocess.run(
        ["git", "-C", str(reference), "-c", f"safe.directory={reference.as_posix()}", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def terminal_excerpt(text: str, *, limit: int = 300, width: int = 88) -> str:
    """Return a compact, wrapped excerpt for readable terminal output."""
    excerpt = " ".join(text.split())
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return textwrap.fill(
        excerpt,
        width=width,
        initial_indent="     ",
        subsequent_indent="     ",
        break_long_words=False,
        break_on_hyphens=False,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", default=[], help="May be repeated for multiple questions")
    parser.add_argument("--query-file", type=Path, help="UTF-8 file with one query per line")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/processed/corpus.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/predictions/manual_top5.csv")
    args = parser.parse_args()
    if args.query_file:
        args.query.extend(line.strip() for line in args.query_file.read_text(encoding="utf-8").splitlines() if line.strip())
    if not args.query:
        parser.error("provide --query or --query-file")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    index = InvertedIndex(); index.build(corpus)
    methods = {"boolean": BooleanRetriever(index), "tfidf": TfidfRetriever(), "bm25": BM25Retriever()}
    methods["tfidf"].fit(corpus); methods["bm25"].fit(corpus)
    rows = []
    for query_no, query in enumerate(args.query, 1):
        for name, model in methods.items():
            print(f"\n[{name.upper()}] {query}")
            for rank, result in enumerate(model.search(query, top_k=args.top_k), 1):
                doc_id = str(result.get("doc_id", result.get("cid")))
                snippet = " ".join(corpus[doc_id].split())[:300]
                row = {"query_no": query_no, "query": query, "method": name,
                       "rank": rank, "doc_id": doc_id, "score": float(result["score"]),
                       "snippet": snippet}
                rows.append(row)
                print(f"  {rank:>2}. ID: {doc_id}  |  score: {result['score']:.6f}")
                print(terminal_excerpt(snippet))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["query_no", "query", "method", "rank", "doc_id", "score", "snippet"])
        writer.writeheader(); writer.writerows(rows)
    query_hashes = {"query_file_sha256": file_sha256(args.query_file)} if args.query_file else {}
    config = {
        "reference_revision": reference_revision(),
        "corpus_sha256": file_sha256(args.corpus),
        "top_k": args.top_k,
        "query_count": len(args.query),
        "methods": list(methods),
        "prediction_count": len(rows),
        "unique_queries": len({row["query_no"] for row in rows}),
        "unique_methods": sorted({row["method"] for row in rows}),
        "output_sha256": file_sha256(args.output),
        **query_hashes,
    }
    args.output.with_name("manual_top5_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved {len(rows)} ranked rows to {args.output}")


if __name__ == "__main__":
    main()
