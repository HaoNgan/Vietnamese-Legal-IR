# Tiến trình thực hiện đồ án

**Đề tài:** Nghiên cứu và xây dựng hệ thống truy xuất văn bản pháp luật tiếng Việt sử dụng mô hình biểu diễn ngữ nghĩa và tái xếp hạng.

## Tài liệu này dùng để làm gì?

README hướng dẫn cài đặt và chạy dự án. File này tóm tắt những phần đã làm, kết quả thu được và nơi lưu bằng chứng để tiện xem lại tiến độ.

## Tiến độ hiện tại

| Mốc | Nội dung | Trạng thái |
|---|---|---|
| G0 | Chạy thử Boolean, TF-IDF và BM25 trên dữ liệu BKAI/YuITC giới hạn | Hoàn tất theo phạm vi thử nghiệm |
| G1 | Chuẩn hóa dữ liệu Zalo 2021, khóa split, checksum và evaluator | Hoàn tất |
| G2 / B0 | Chạy BM25 trên corpus Zalo và đánh giá trên validation | Hoàn tất |
| G3 / B1 | Chạy BGE-M3 + FAISS trên toàn corpus và đánh giá trên validation | Hoàn tất |

## G0 — Baseline ban đầu

G0 kiểm tra khả năng chạy truy xuất và xem kết quả Top-K trên tập dữ liệu giới hạn:

- 5.000 văn bản BKAI; 500 query/qrel YuITC được chuẩn bị.
- Metric được tính trên 100 query.
- Các phương pháp: Boolean, TF-IDF và BM25.

| Phương pháp | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|
| Boolean | 0,2050 | 0,1912 | 0,1960 |
| TF-IDF | 0,8800 | 0,7394 | 0,7795 |
| BM25 | 0,9450 | 0,8485 | 0,8767 |

**Lưu ý:** Đây là kết quả trên subset BKAI/YuITC, không phải kết quả trên benchmark Zalo. Một số baseline gọi mã từ repository tham khảo đã pin revision; không phải toàn bộ được tự cài đặt từ đầu.

**Xem kết quả tại:** `outputs/reports/baseline_g0/`, `outputs/predictions/baseline_g0/` và `docs/g0_topk_evidence.md`.

## G1 — Khóa dữ liệu và evaluator

Benchmark chính là Zalo AI Legal Text Retrieval 2021:

- 61.425 văn bản và 3.196 query.
- Train: 2.300 query; validation: 256 query; test chính thức: 640 query.
- Metric: Recall@10, Recall@50, MRR, MAP và nDCG@10.
- Split test được giữ riêng, chưa dùng để chọn cấu hình hoặc báo cáo điểm test.

Đã kiểm tra schema, ID, qrels, checksum và evaluator. Lệnh xác minh dữ liệu chạy thành công:

```powershell
python -m src.data.prepare_g1 --verify
```

**Xem cấu hình và bằng chứng tại:** `configs/g1_data_lock.json`, `data/processed/benchmarks/zalo_2021/manifest.json` và `outputs/reports/g1_data_lock/`.

## G2 / B0 — BM25 trên Zalo

BM25 được chạy trên toàn bộ 61.425 văn bản và đánh giá bằng 256 query validation. Chín cấu hình được so sánh; cấu hình chọn theo nDCG@10 validation là `k1=1.2, b=0.75`.

| Cấu hình | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| Mặc định `k1=1.5, b=0.75` | 0,859375 | 0,949219 | 0,618477 | 0,618477 | 0,672548 |
| Chọn `k1=1.2, b=0.75` | 0,855469 | 0,949219 | 0,623093 | 0,623093 | 0,675143 |

Cấu hình chọn có nDCG@10 cao hơn một chút, nhưng Recall@10 thấp hơn. Vì vậy không kết luận cấu hình này tốt hơn trên mọi metric.

Lệnh chạy:

```powershell
python -m src.evaluation.run_bm25 --top-k 100 --output-dir outputs/bm25_zalo_validation_20261028
```

**Xem index, predictions, metric, cấu hình và log tại:** `outputs/bm25_zalo_validation_20261028/`.

## G3 / B1 — BGE-M3 và FAISS

Máy Windows không có GPU phù hợp để encode corpus trong thời gian khả thi, nên B1 được chạy trên Kaggle GPU Tesla T4. Checkpoint sử dụng là `BAAI/bge-m3`; toàn bộ 61.425 văn bản được encode thành vector 1.024 chiều, chuẩn hóa và đưa vào FAISS `IndexFlatIP`.

- Encode đủ 61.425/61.425 văn bản, lưu thành 960 shard.
- Truy xuất và đánh giá trên 256 query validation; mỗi query có tối đa 100 kết quả.
- Index có 61.425 vector; mapping có 61.425 CID duy nhất theo thứ tự corpus.
- Đã tải artifact về, kiểm tra checksum, nạp lại FAISS trên Windows và chạy lại evaluator.

| Phương pháp | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| B0 BM25 | 0,855469 | 0,949219 | 0,623093 | 0,623093 | 0,675143 |
| B1 BGE-M3 + FAISS | 0,921875 | 0,968750 | 0,717058 | 0,717058 | 0,764762 |

Trong lần chạy này, B1 có điểm cao hơn B0 trên các metric trên validation. Đây chưa phải kết quả trên test và chưa chứng minh mức chênh lệch có ý nghĩa thống kê.

| Đo đạc B1 | Kết quả |
|---|---:|
| Thời gian chạy Kaggle | 5.437,3 giây |
| Thời gian encode corpus | 5.294,886 giây |
| FAISS build/save | 0,506 giây |
| Query latency p50 / p95 | 53,496 / 60,511 ms |
| Kích thước FAISS index | 251.596.845 byte |

Query latency gồm encode query và FAISS search, không gồm thời gian encode corpus. Latency B0 được đo trong môi trường khác, nên không dùng hai số này để kết luận hệ nào nhanh hơn.

**Xem artifact B1 tại:** `outputs/b1_dense_validation/`. Gói tải về là `B1_BGE_M3_FAISS_validation_artifacts.zip`; kết quả đánh giá lại được lưu tại `metrics_recomputed_local.json`.

## Kiểm thử và giới hạn hiện tại

- `python -m unittest discover -s tests -v`: 13 test đạt, gồm kiểm tra BM25, evaluator, FAISS, mapping và shard.
- Đã chạy B1 end-to-end trên dữ liệu thật và nạp lại index trên Windows.
- Kết quả G0 dùng subset; kết quả G2/G3 dùng validation Zalo. Không gộp G0 với B0/B1 để so sánh trực tiếp.
- Qrels test chưa được dùng để đánh giá.
- Hybrid retrieval và Cross-Encoder reranking mới xuất hiện trong sơ đồ kiến trúc tham khảo; chưa được tích hợp và đánh giá trong các mốc trên.

## Sơ đồ kiến trúc tham khảo

Đã đọc mã nguồn `chisngooo/Vietnamese-Legal-Document-Retrieval` tại revision `366e8fb978d97b773d1cd16a92cc0de5445208dd` để hiểu cách ghép BM25, dense retrieval, fusion và reranking. Sơ đồ trong `docs/research_architecture.svg` dùng để minh họa pipeline; không có nghĩa các bước fusion và reranking đã được triển khai trong B1.
