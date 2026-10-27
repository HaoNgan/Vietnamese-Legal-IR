import math
import unittest

from src.evaluation.metrics import average_precision, ndcg_at_k, query_metrics, recall_at_k, reciprocal_rank


class RetrievalMetricTests(unittest.TestCase):
    def test_binary_metrics_against_hand_calculation(self):
        qrels = {"a": 1, "c": 1}
        ranked = ["a", "b", "c"]
        self.assertEqual(recall_at_k(ranked, qrels, 2), 0.5)
        self.assertEqual(recall_at_k(ranked, qrels, 50), 1.0)
        self.assertEqual(reciprocal_rank(ranked, qrels), 1.0)
        self.assertAlmostEqual(average_precision(ranked, qrels), 5 / 6)
        self.assertAlmostEqual(ndcg_at_k(ranked, qrels, 10), 1.5 / (1 + 1 / math.log2(3)))

    def test_graded_ndcg_uses_exponential_gain(self):
        qrels = {"a": 2, "b": 1}
        expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
        self.assertAlmostEqual(ndcg_at_k(["b", "a"], qrels, 10), expected)

    def test_unreturned_relevant_documents_reduce_recall_and_ap(self):
        qrels = {"a": 1, "b": 1}
        self.assertEqual(recall_at_k(["a"], qrels, 10), 0.5)
        self.assertEqual(average_precision(["a"], qrels), 0.5)

    def test_macro_metric_bundle(self):
        result = query_metrics(["x"], {"x": 1})
        self.assertEqual(result["recall@10"], 1.0)
        self.assertEqual(result["recall@50"], 1.0)
        self.assertEqual(result["mrr"], 1.0)
        self.assertEqual(result["map"], 1.0)
        self.assertEqual(result["ndcg@10"], 1.0)

    def test_empty_relevance_is_rejected(self):
        with self.assertRaises(ValueError):
            recall_at_k([], {}, 10)


if __name__ == "__main__":
    unittest.main()
