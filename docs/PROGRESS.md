# Tiến độ đồ án

Đồ án xây dựng công cụ tìm văn bản pháp luật tiếng Việt. Người dùng nhập câu hỏi; hệ thống tìm các văn bản liên quan và xếp chúng theo mức độ phù hợp.

## Đã thực hiện

| Mốc | Việc đã làm | Kết quả |
|---|---|---|
| G0 | Chạy thử Boolean, TF-IDF, BM25 trên tập con BKAI/YuITC | Kiểm tra được truy vấn Top-K và evaluator; metric tính trên 100 query. |
| G1 | Chuẩn hóa benchmark Zalo, kiểm tra dữ liệu và khóa split/evaluator | Corpus 61.425 văn bản; 2.300 query train, 256 validation, 640 test. |
| G2 / B0 | Chạy BM25 trên corpus Zalo và so sánh 9 cấu hình bằng validation | Chọn `k1=1.2, b=0.75` theo nDCG@10. |
| G3 / B1 | Encode toàn corpus bằng BGE-M3, lập FAISS và chạy validation | Có 61.425 vector, mapping CID, predictions, metric và latency. |

## Kết quả chính trên validation Zalo

| Phương pháp | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| B0 BM25 | 0,855469 | 0,949219 | 0,623093 | 0,623093 | 0,675143 |
| B1 BGE-M3 + FAISS | 0,921875 | 0,968750 | 0,717058 | 0,717058 | 0,764762 |

Các điểm số dùng cùng 256 query validation và evaluator. B1 cao hơn B0 trong lần đánh giá này; chưa có kết quả trên test nên không kết luận cho test. Latency B0 và B1 đo trên môi trường khác nhau, không dùng để so sánh tốc độ.

G0 dùng subset BKAI/YuITC riêng, nên không so sánh trực tiếp metric G0 với kết quả Zalo.

## Mở kết quả và bằng chứng

- G0 Top-5 thủ công: [g0_topk_evidence.md](g0_topk_evidence.md), cùng log và CSV trong `docs/evidence/`.
- BM25 B0: `outputs/bm25_zalo_validation_20261028/metrics_comparison.csv`.
- Dense B1: `outputs/b1_dense_validation/` — FAISS index, CID mapping, predictions, metrics và cấu hình chạy.
- Kiểm tra nghiệm thu B1: [g3_acceptance.md](reports/g3_acceptance.md).
- Dữ liệu đã khóa: `data/processed/benchmarks/zalo_2021/manifest.json` và `configs/g1_data_lock.json`.

## Phần chưa triển khai

Chưa đánh giá 640 query test. Hybrid retrieval, Cross-Encoder reranking như một bước chạy được trong hệ thống, và Web/API cũng chưa được triển khai. Sơ đồ kiến trúc chỉ minh họa luồng dự kiến, không phải bằng chứng các phần đó đã chạy.
