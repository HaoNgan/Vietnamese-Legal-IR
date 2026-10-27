import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.loaders import write_jsonl
from src.evaluation.evaluate_runs import load_run, main


class RunEvaluatorTests(unittest.TestCase):
    def test_ranked_run_rejects_rank_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run.csv"
            run.write_text("qid,doc_id,rank\nq1,d1,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_run(run, {"d1"})

    def test_cli_macro_averages_every_qid_in_qrels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qrels = root / "qrels.jsonl"
            corpus = root / "corpus.jsonl"
            run = root / "run.csv"
            output = root / "report.json"
            write_jsonl(qrels, [
                {"qid": "q1", "doc_id": "d1", "relevance": 1},
                {"qid": "q1", "doc_id": "d3", "relevance": 1},
                {"qid": "q2", "doc_id": "d2", "relevance": 1},
            ])
            write_jsonl(corpus, [{"doc_id": d, "text": "document"} for d in ("d1", "d2", "d3")])
            with run.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["qid", "doc_id", "rank", "score"])
                writer.writeheader()
                writer.writerows([
                    {"qid": "q1", "doc_id": "d1", "rank": 1, "score": 2.0},
                    {"qid": "q1", "doc_id": "d2", "rank": 2, "score": 1.0},
                    {"qid": "q1", "doc_id": "d3", "rank": 3, "score": 0.5},
                ])
            with patch("sys.argv", ["evaluate_runs", "--qrels", str(qrels), "--run", str(run),
                                    "--corpus", str(corpus), "--output", str(output)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["queries"], 2)
            self.assertEqual(report["queries_without_results_scored_as_empty"], 1)
            metrics = report["metrics_macro_average"]
            self.assertEqual(metrics["recall@10"], 0.5)
            self.assertEqual(metrics["recall@50"], 0.5)
            self.assertEqual(metrics["mrr"], 0.5)
            self.assertAlmostEqual(metrics["map"], 5 / 12)
            self.assertAlmostEqual(metrics["ndcg@10"], (1.5 / (1 + 1 / __import__("math").log2(3))) / 2)


if __name__ == "__main__":
    unittest.main()
