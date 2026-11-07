# Báo cáo nghiệm thu G3 — B1 Dense Retrieval

## Kết quả

B1 chạy trên toàn bộ corpus Zalo bằng BGE-M3 và FAISS. Index được lưu, tải về và nạp lại trên Windows. Mapping CID, predictions, metric và latency đều có artifact để kiểm tra.

**Phạm vi:** 256 query validation đã khóa ở G1. 640 query test chưa được đánh giá; kết luận này chỉ áp dụng cho validation.

## Thiết lập

| Thành phần | Thiết lập |
|---|---|
| Corpus | Zalo 2021, 61.425 văn bản |
| Tập đánh giá | Validation, 256 query; tối đa 100 kết quả/query |
| Mô hình | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181` |
| GPU | Kaggle Tesla T4, CUDA 12.8; phiên chạy dùng CUDA device 0 |
| Embedding | float32, 1.024 chiều, L2-normalized |
| Similarity | Inner product trên vector đã chuẩn hóa, tương đương cosine similarity |
| FAISS | Exact search bằng `IndexFlatIP` |
| Shard | 64 văn bản/shard; 960/960 shard đã xử lý |
| Batch và độ dài đầu vào | Batch size 1; max sequence length 8.192 |
| Phần mềm | Python 3.13.15, PyTorch 2.11.0+cu128, Sentence Transformers 5.7.0, FAISS 1.15.1 |

## Kết quả B0 và B1

| Phương pháp | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 | Latency p50/p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| B0 BM25 (`k1=1.2, b=0.75`) | 0,855469 | 0,949219 | 0,623093 | 0,623093 | 0,675143 | 152,780 / 279,512 |
| B1 BGE-M3 + FAISS | 0,921875 | 0,968750 | 0,717058 | 0,717058 | 0,764762 | 53,496 / 60,511 |

Hai phương pháp được chấm trên cùng 256 query validation bằng evaluator của dự án. B1 có metric cao hơn B0 trong lần đánh giá này; chưa có kết quả test và chưa kiểm định ý nghĩa thống kê.

B1 latency gồm mã hóa query và tìm kiếm FAISS, không gồm encode corpus. B0 và B1 được đo trên môi trường khác nhau, nên không dùng latency để kết luận phương pháp nào nhanh hơn.

## Thời gian và tài nguyên B1

| Số đo | Kết quả |
|---|---:|
| Tổng thời gian notebook | 5.437,3 giây |
| Encode corpus | 5.294,886 giây |
| Build và lưu FAISS | 0,506 giây |
| FAISS index | 251.596.845 byte |
| Mapping CID | 1.576.182 byte |
| Peak working set | 4.084.269.056 byte |
| Peak GPU memory allocated | 2.683.638.784 byte |

## Kiểm tra artifact

Gói Kaggle được tải về `outputs/b1_dense_validation/B1_BGE_M3_FAISS_validation_artifacts.zip`:

- Kích thước 240.244.275 byte; SHA-256 `4f8e50364b5049a2f43122acb7ec6a5fcc63fbe80e91b78b3bf174161842cb8f`.
- ZIP mở và kiểm tra được; SHA-256 và kích thước của 9 artifact trong manifest khớp.
- Checksum corpus, query, qrels validation và manifest khớp dữ liệu G1 trong workspace.
- FAISS nạp trên Windows với 61.425 vector, chiều 1.024, kiểu `IndexFlatIP`.
- Mapping có 61.425 CID duy nhất theo đúng thứ tự corpus.
- Predictions có 25.600 dòng: 256 query, 100 kết quả/query; rank liên tục, score giảm dần, CID hợp lệ và không lặp trong một query.
- Chạy lại evaluator trên predictions và qrels validation cho kết quả khớp `metrics.json` sau khi làm tròn.
- `python -m unittest discover -s tests -v`: 13 test đạt, gồm regression BM25, evaluator/metrics và dense/FAISS/shard.

Các artifact đã giải nén nằm trong `outputs/b1_dense_validation/`, gồm index, mapping, predictions, metrics, so sánh B0/B1, cấu hình và manifest. Metric kiểm tra lại trên Windows nằm trong `metrics_recomputed_local.json`.

## Giới hạn và cách chạy lại

- Chưa đánh giá 640 query test; không dùng test qrels để chọn cấu hình.
- FAISS exact full precision chiếm khoảng 240 MiB; artifact lớn được giữ trong `outputs/`, không nên commit lên Git.
- Để chạy lại trên Kaggle, dùng notebook B1 và dataset đầu vào đã xác minh, bật GPU T4 rồi chọn **Save & Run All**.
- Để chạy trong môi trường cục bộ đã cài dependencies, dùng `python -m experiments.B1_dense`. Dùng `python -m experiments.B1_dense --reuse-index` để nạp index đã có theo cấu hình.

**Kết luận:** có bằng chứng cho encode đủ corpus, FAISS, mapping, predictions, metric, latency và nạp lại trên Windows. G3 được nghiệm thu cho B1 trên validation; chưa có kết quả test.
