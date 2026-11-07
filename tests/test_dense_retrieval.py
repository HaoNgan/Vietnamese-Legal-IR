import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np

# The BM25 runner prepends its pinned reference checkout to src.retrieval.
# Keep this test pointed at the project's own dense modules in the same process.
import src
LOCAL_SRC = str(Path(__file__).resolve().parents[1] / "src")
src.__path__ = [LOCAL_SRC, *[path for path in src.__path__ if path != LOCAL_SRC]]
if "src.retrieval" in sys.modules:
    LOCAL_RETRIEVAL = str(Path(LOCAL_SRC) / "retrieval")
    if LOCAL_RETRIEVAL not in list(sys.modules["src.retrieval"].__path__):
        sys.modules["src.retrieval"].__path__.append(LOCAL_RETRIEVAL)

from src.retrieval.dense import encode_corpus_sharded, retrieve, shard_encoding_timing
from src.retrieval.faiss_index import FaissVectorIndex


FAISS_AVAILABLE = importlib.util.find_spec("faiss") is not None


class DenseRetrievalTests(unittest.TestCase):
    @unittest.skipUnless(FAISS_AVAILABLE, "faiss-cpu is not installed")
    def test_faiss_mapping_order_and_save_load(self):
        vectors = np.asarray([[1, 0], [0, 1], [.8, .6]], dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        index = FaissVectorIndex.build(vectors, ["a", "b", "c"])
        self.assertEqual(index.search(np.asarray([1, 0], np.float32), 3)[0][0][0], "a")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "index.faiss"
            index.save(path)
            loaded = FaissVectorIndex.load(path)
        self.assertEqual(loaded.document_ids, ["a", "b", "c"])
        self.assertEqual(loaded.search(np.asarray([1, 0], np.float32), 3), index.search(np.asarray([1, 0], np.float32), 3))

    @unittest.skipUnless(FAISS_AVAILABLE, "faiss-cpu is not installed")
    def test_faiss_rejects_bad_ids_and_vectors(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            FaissVectorIndex.build(np.asarray([[1, 0], [0, 1]], np.float32), ["a", "a"])
        with self.assertRaisesRegex(ValueError, "normalized"):
            FaissVectorIndex.build(np.asarray([[2, 0]], np.float32), ["a"])
        valid = FaissVectorIndex.build(np.asarray([[1, 0]], np.float32), ["a"])
        with self.assertRaisesRegex(ValueError, "dimension"):
            valid.search(np.asarray([1, 0, 0], np.float32), 1)
        self.assertEqual(valid.search(np.asarray([1, 0], np.float32), 0), [[]])


    def test_sharded_embedding_reuses_valid_shard_and_detects_bad_corpus(self):
        docs = [{"doc_id": "a", "text": "x"}, {"doc_id": "b", "text": "y"}]
        encoder = FakeEncoder()
        with tempfile.TemporaryDirectory() as tmp:
            vectors, ids = encode_corpus_sharded(encoder, docs, tmp, batch_size=1, shard_size=1)
            self.assertEqual(vectors.shape, (2, 2))
            self.assertEqual(ids, ["a", "b"])
            self.assertEqual(encoder.calls, 2)
            timing = shard_encoding_timing(tmp, document_count=2, shard_size=1)
            self.assertTrue(timing["complete"])
            self.assertEqual(timing["shards"], 2)
            self.assertIsNotNone(timing["encoder_seconds"])
            encode_corpus_sharded(encoder, docs, tmp, batch_size=1, shard_size=1)
            self.assertEqual(encoder.calls, 2)
            self.assertEqual(shard_encoding_timing(tmp, 2, 1), timing)
        with self.assertRaisesRegex(ValueError, "unique"):
            encode_corpus_sharded(encoder, [docs[0], docs[0]], Path(tmp) / "other")

    @unittest.skipUnless(FAISS_AVAILABLE, "faiss-cpu is not installed")
    def test_retrieve_returns_ranked_rows_and_empty_query(self):
        index = FaissVectorIndex.build(np.asarray([[1, 0], [0, 1]], np.float32), ["a", "b"])

        class Encoder:
            def encode(self, texts):
                return np.asarray([[1, 0]], np.float32)

        rows, latency = retrieve(Encoder(), index, {"q1": "query", "q2": " "}, 2)
        self.assertEqual([(r["qid"], r["doc_id"], r["rank"]) for r in rows], [("q1", "a", 1), ("q1", "b", 2)])
        self.assertEqual(len(latency), 2)
        self.assertGreaterEqual(latency[0], 0)


class FakeEncoder:
    class model:
        @staticmethod
        def get_sentence_embedding_dimension():
            return 2

    def __init__(self):
        self.calls = 0

    def encode(self, texts, batch_size=32):
        self.calls += 1
        return np.tile(np.asarray([[1, 0]], np.float32), (len(texts), 1))
