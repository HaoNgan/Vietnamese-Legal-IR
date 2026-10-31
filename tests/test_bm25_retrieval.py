import tempfile
import unittest
from pathlib import Path

from src.evaluation.run_bm25 import BM25Retriever


class BM25RetrievalTests(unittest.TestCase):
    def test_index_round_trip_preserves_ranked_ids_and_scores(self):
        corpus = {
            "law-20": "Điều kiện đăng ký kết hôn phải đủ tuổi theo quy định pháp luật.",
            "law-10": "Quy định về thuế thu nhập doanh nghiệp và hóa đơn.",
            "law-30": "Đăng ký kết hôn khi đủ tuổi theo luật hôn nhân gia đình.",
        }
        retriever = BM25Retriever(k1=1.5, b=0.75)
        retriever.fit(corpus)
        first = retriever.search("đăng ký kết hôn đủ tuổi", top_k=3)
        second = retriever.search("đăng ký kết hôn đủ tuổi", top_k=3)

        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertTrue({row["doc_id"] for row in first}.issubset(corpus))

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "bm25_index.pkl"
            retriever.save(index_path)
            loaded = BM25Retriever.load(index_path)
            restored = loaded.search("đăng ký kết hôn đủ tuổi", top_k=3)

        self.assertEqual(first, restored)


if __name__ == "__main__":
    unittest.main()
