"""Standard information-retrieval metrics for ranked document IDs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _relevance(qrels: Mapping[str, int]) -> dict[str, int]:
    return {str(doc_id): int(value) for doc_id, value in qrels.items() if int(value) > 0}


def recall_at_k(ranked: Sequence[str], qrels: Mapping[str, int], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = _relevance(qrels)
    if not relevant:
        raise ValueError("Recall is undefined for a query without relevant documents")
    return len(set(map(str, ranked[:k])) & relevant.keys()) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], qrels: Mapping[str, int]) -> float:
    relevant = _relevance(qrels)
    if not relevant:
        raise ValueError("MRR is undefined for a query without relevant documents")
    for rank, doc_id in enumerate(ranked, start=1):
        if str(doc_id) in relevant:
            return 1.0 / rank
    return 0.0


def average_precision(ranked: Sequence[str], qrels: Mapping[str, int]) -> float:
    relevant = _relevance(qrels)
    if not relevant:
        raise ValueError("MAP is undefined for a query without relevant documents")
    seen: set[str] = set()
    hit_count = 0
    precision_sum = 0.0
    for rank, doc_id in enumerate(ranked, start=1):
        doc_id = str(doc_id)
        if doc_id in relevant and doc_id not in seen:
            seen.add(doc_id)
            hit_count += 1
            precision_sum += hit_count / rank
    return precision_sum / len(relevant)


def ndcg_at_k(ranked: Sequence[str], qrels: Mapping[str, int], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = _relevance(qrels)
    if not relevant:
        raise ValueError("nDCG is undefined for a query without relevant documents")

    def gain(relevance: int) -> float:
        return (2**relevance) - 1

    dcg = sum(
        gain(relevant.get(str(doc_id), 0)) / math.log2(rank + 1)
        for rank, doc_id in enumerate(ranked[:k], start=1)
    )
    ideal = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum(gain(value) / math.log2(rank + 1) for rank, value in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def query_metrics(ranked: Sequence[str], qrels: Mapping[str, int]) -> dict[str, float]:
    return {
        "recall@10": recall_at_k(ranked, qrels, 10),
        "recall@50": recall_at_k(ranked, qrels, 50),
        "mrr": reciprocal_rank(ranked, qrels),
        "map": average_precision(ranked, qrels),
        "ndcg@10": ndcg_at_k(ranked, qrels, 10),
    }
