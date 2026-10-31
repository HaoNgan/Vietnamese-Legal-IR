# Tiến độ đồ án

Cập nhật: 28/10/2026. Trạng thái dưới đây dựa trên lệnh, mã nguồn và artifact đã kiểm tra trong repository.

## Tóm tắt

| Tuần / Gate | Trạng thái | Kết luận |
|---|---|---|
| Tuần 1 / G0 | **Đạt** | Baseline 100 query và truy vấn Top-K đã chạy lại, predictions/metric khớp byte với artifact trước. Người dùng xác nhận đã tự vẽ và giải thích sơ đồ pipeline theo yêu cầu G0.4. |
| Tuần 2 / G1 | **Đạt** | Benchmark Zalo, split, checksum và evaluator đã xác minh; 9 test hiện có đều đạt. Đây chưa phải kết quả retrieval. |
| Tuần 3 / G2 | **Đạt** | BM25 B0 fit trên toàn corpus; 9 cấu hình được chấm trên validation. Replay từ index tạo lại byte-for-byte cả 9 predictions và metric. Chưa đánh giá test; không kết luận khả năng khái quát. |

## Tuần 1 — G0: baseline và Top-K

### Mục tiêu

Chạy Boolean, TF-IDF và BM25; đánh giá 100 query; xem Top-K; ghi lại cách chạy và pipeline.

### Công việc và bằng chứng

- Tập G0 gồm 5.000 tài liệu BKAI và 500 query/qrel YuITC; lần đánh giá dùng 100 query.
- Đã chạy lại trong `.venv`, lưu riêng tại `outputs/g0_repro_check/`. SHA-256 của reference revision, corpus, queries, qrels, predictions và report metric khớp artifact G0 đã lưu trước đó.
- Kết quả trên 100 query:

| Phương pháp | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|
| Boolean | 0.2050 | 0.1912 | 0.1960 |
| TF-IDF | 0.8800 | 0.7394 | 0.7795 |
| BM25 | 0.9450 | 0.8485 | 0.8767 |

- Đã chạy lại 10 query thủ công × 3 phương pháp, Top-5. Có 115 dòng kết quả vì Boolean chỉ trả kết quả cho 3/10 query; SHA-256 CSV/input khớp lần chạy đã lưu. Bản tái chạy ở `outputs/g0_repro_check/manual_top5.csv`.
- Artifact G0 ban đầu: `outputs/reports/baseline_g0/`, `outputs/predictions/baseline_g0/`, `docs/evidence/g0_topk_terminal.log`, `docs/evidence/g0_topk_results.csv`.
- Lệnh baseline: `python -m src.evaluation.run_baselines --max-queries 100 --top-k 10`. Lệnh Top-K: `python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5`.
- Boolean/TF-IDF/BM25 gọi mã repository Daijestic tại revision `92fc24310adf26fd401573003028689e5cacc289`; đây là mã tham khảo đã tích hợp, không phải implementation mới tự viết.
- README có mô tả pipeline, lệnh chạy và giới hạn của metric. Người dùng xác nhận đã tự vẽ và giải thích pipeline theo yêu cầu G0.4.

**Trạng thái G0: Đạt.** Baseline và Top-K tái lập được; G0.4 được người dùng xác nhận. File hướng dẫn gốc và nội dung “Mục 13” không có trong cây dự án trên ổ D, nên phần còn lại được đối chiếu theo checklist và tài liệu hướng dẫn đã cung cấp.

## Tuần 2 — G1: khóa benchmark và evaluator

### Đã kiểm chứng

- Benchmark: Zalo AI Legal Text Retrieval 2021, revision `5fb3df4300b3a81455fe09af444ec159afa8d212`.
- Corpus: 61.425 tài liệu; 3.196 query. Split: 2.300 train, 256 validation, 640 test. Seed chia split: `zalo-g1-v1`; test giữ nguyên.
- Schema chuẩn: corpus `doc_id/title/text`; query `qid/query`; qrels `qid/doc_id/relevance`.
- Manifest ghi checksum SHA-256 cho 6 artifact xử lý và 7 artifact nguồn, số lượng và integrity checks. Có 1.277 dòng tài liệu trùng nguyên văn sau chuẩn hóa và 357 tài liệu rỗng được giữ lại.
- Không có qid giao train/test hoặc query trùng chính xác sau chuẩn hóa giữa các split. Kiểm tra exact match không phát hiện paraphrase/gần trùng ngữ nghĩa.
- Đã chạy thành công:

```powershell
.\.venv\Scripts\python.exe -m src.data.prepare_g1 --verify
```

Kết quả: `G1 lock verified`; 6 processed artifacts và 7 pinned source artifacts khớp checksum.

- Evaluator hỗ trợ Recall@10, Recall@50, MRR, MAP và nDCG@10. Cả 9 test evaluator/metric/retrieval hiện có đều đạt; có kiểm tra evaluator từ chối document ID không có trong corpus.
- Báo cáo/manifest: `outputs/reports/g1_data_lock/dataset_report.md`, `outputs/reports/g1_data_lock/manifest.json`, `data/processed/benchmarks/zalo_2021/manifest.json`, `configs/g1_data_lock.json`.

**Trạng thái G1: Đạt.** Đây là khóa dữ liệu, split, checksum và evaluator; không phải điểm retrieval. Test qrels hiện diện cục bộ nhưng không được đọc để chọn BM25.

## Tuần 3 — G2: BM25 B0 trên Zalo

### Thiết lập

- Đánh giá trên 61.425 tài liệu và 256 query validation; mỗi query truy xuất tối đa 100 kết quả để chấm Recall@10/50, MRR, MAP và nDCG@10.
- Dùng `BM25Retriever` tại revision `92fc24310adf26fd401573003028689e5cacc289`. Preprocessing theo mã tham khảo: `clean_text` → Underthesea `word_tokenize` → reference stopword removal. Index ghép `title` và `text`.
- Baseline mặc định `k1=1.5`, `b=0.75`; grid `k1={1.2,1.5,1.8}` × `b={0.5,0.75,1.0}`. Chọn theo nDCG@10 validation; tie-break theo MAP, MRR, Recall@10, Recall@50 rồi p95 latency thấp hơn.
- Không fit BM25 trên query/qrels; không dùng test để chọn tham số. Seed ngẫu nhiên cho BM25 không áp dụng; split seed được ghi trong manifest G1.

### Kết quả validation

| Cấu hình | k1 | b | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 | Latency p50/p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mặc định | 1.5 | 0.75 | 0.8594 | 0.9492 | 0.6185 | 0.6185 | 0.6725 | 158.565 / 317.389 |
| Chọn trên validation | 1.2 | 0.75 | 0.8555 | 0.9492 | 0.6231 | 0.6231 | 0.6751 | 165.624 / 304.356 |

Cấu hình được chọn tăng nDCG@10 **0.0026** và MAP/MRR **0.0046**, giữ Recall@50 nhưng giảm Recall@10 **0.0039**. Mức thay đổi nhỏ trên 256 query validation; đây không phải bằng chứng cải thiện có ý nghĩa thống kê hay khái quát sang test. Toàn bộ 9 cấu hình và latency nằm trong `outputs/bm25_zalo_validation_20261028/metrics_comparison.csv`.

Latency tính cho một search/query khi index đã nạp, gồm preprocessing query và query đầu tiên; không gồm fit/load index hay ghi file. Thời gian fit toàn corpus hiển thị trên progress bar là khoảng **35:02**; lần chạy đầu lỗi trước khi timer cấu trúc được lưu. Phần provenance giải thích chi tiết tại `outputs/bm25_zalo_validation_20261028/index_build_provenance.json`.

### Kiểm chứng và artifact

- Runner: `src/evaluation/run_bm25.py`. Runner fit một lần, quét grid trên validation, kiểm tra IDs/ranks/depth bằng loader của evaluator; lưu index, predictions, metric tổng hợp/theo query, checksum, config và log.
- Test `tests/test_bm25_retrieval.py` kiểm tra ranking ổn định, mapping ID và kết quả sau save/load; toàn bộ 9 unit test đạt.
- Lượt fit + sweep đầu đã lưu index 91.617.306 byte và tất cả predictions, nhưng dừng ở bước cuối ghi metadata do output path tương đối. Sau khi sửa path, runner nạp index và chạy lại cả 9 cấu hình.
- SHA-256 predictions của cả 9 cấu hình và cả 5 metric mỗi cấu hình trùng chính xác giữa hai lượt. Evaluator CLI độc lập cho baseline và cấu hình chọn chấm đủ 256/256 qid, không có qid thiếu, metric khớp report. Độ sâu run quan sát được là 85–100 kết quả/query. Benchmark có một positive qrel mỗi query nên MRR và MAP bằng nhau. Artifact nằm trong `outputs/bm25_zalo_validation_20261028/`, gồm index, predictions, `metrics_comparison.csv`, `per_query/`, `standalone_evaluation/`, config, log và snapshot runner.
- Môi trường đã ghi trong `run_config.json`: Python 3.10.0, Windows 10, 4 logical CPUs, Underthesea 6.8.4; reference revision nêu trên. Checksum inputs gắn với manifest/dữ liệu khóa.

### Bước kế tiếp

- Giữ test split chưa mở cho đến khi protocol đánh giá cuối được cố định; sau đó chỉ đánh giá test một lần, không quay lại chọn tham số từ test.
- Grid hiện tại hẹp; các kết luận chỉ giới hạn ở 9 cấu hình và validation. Nếu thử preprocessing hoặc grid khác, tiếp tục chọn trên validation.
- **Trạng thái G2: Đạt theo tiêu chí đã giao** — B0 chạy trên corpus benchmark khóa; chạy lại từ index tái tạo đúng predictions/metric. Kết quả chỉ là validation; test vẫn được giữ lại cho đánh giá cuối và không có claim về generalization.

### Lệnh chạy lại

```powershell
# Fit index từ corpus khóa và chạy 9 cấu hình validation
.\.venv\Scripts\python.exe -m src.evaluation.run_bm25 --top-k 100 --output-dir outputs\bm25_zalo_validation_20261028

# Nạp index đã lưu và tái tạo predictions/metric
.\.venv\Scripts\python.exe -m src.evaluation.run_bm25 --top-k 100 --reuse-index outputs\bm25_zalo_validation_20261028\bm25_index.pkl --output-dir outputs\bm25_zalo_validation_20261028
```


