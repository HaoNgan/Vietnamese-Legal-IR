# Nghiên cứu và xây dựng hệ thống truy xuất văn bản pháp luật tiếng Việt

**Đề tài:** Nghiên cứu và xây dựng hệ thống truy xuất văn bản pháp luật tiếng Việt sử dụng mô hình biểu diễn ngữ nghĩa và tái xếp hạng
**Repository:** [HaoNgan/Vietnamese-Legal-IR](https://github.com/HaoNgan/Vietnamese-Legal-IR)
**Cập nhật tiến độ:** 28/10/2026

## 1. Mục tiêu đề tài

Xây dựng hệ thống nhận câu hỏi pháp lý bằng tiếng Việt và trả về danh sách xếp hạng các văn bản, điều hoặc khoản có liên quan. Trọng tâm là chất lượng truy xuất và thứ tự kết quả. Sản phẩm cốt lõi không phải chatbot tự sinh tư vấn pháp lý.

Nghiên cứu hướng tới việc so sánh truy xuất từ khóa với truy xuất ngữ nghĩa, sau đó đánh giá việc kết hợp hai nguồn kết quả và tái xếp hạng. Các phương pháp chỉ được kết luận là có ích khi kết quả thực nghiệm trên cùng benchmark và giao thức đánh giá chứng minh điều đó.

## 2. Tiến độ hiện tại

| Giai đoạn | Công việc đã thực hiện | Bằng chứng và trạng thái |
|---|---|---|
| **Tuần 1 · G0 — baseline chạy được** | Chuẩn bị subset BKAI 5.000 văn bản; chạy Boolean, TF-IDF, BM25; tính metric trên 100 query YuITC; chạy lại truy vấn Top-K để kiểm tra tái lập. | Metric và predictions chạy lại trùng checksum lần lưu trước. Người dùng xác nhận đã tự vẽ và giải thích pipeline theo yêu cầu G0.4. |
| **Tuần 2 · G1 — khóa benchmark** | Chuẩn hóa benchmark Zalo; tạo train/validation/test; ghi manifest/checksum; chuẩn bị evaluator; kiểm tra tính toàn vẹn. | Verify thành công: 6 artifact xử lý và 7 artifact nguồn khớp checksum; 9 test hiện có đạt. |
| **Tuần 3 · G2 — BM25 B0** | Fit inverted index trên 61.425 văn bản; so mặc định với lưới 9 cấu hình chỉ trên 256 query validation; lưu index, predictions, metric, config và log. | Cả 9 run replay từ index cho predictions/metric trùng hoàn toàn. Cấu hình chọn trên validation có nDCG@10 0,6751; chưa đánh giá test. Chi tiết tại [`docs/PROGRESS.md`](docs/PROGRESS.md). |

**Phạm vi kết quả hiện có:** G0 là subset BKAI/YuITC. G2 là BM25 trên validation Zalo; không dùng test để chọn tham số và chưa có metric test. Hai nhóm kết quả thuộc hai benchmark khác nhau, không so sánh trực tiếp. Tiến độ và artifact được ghi tại [docs/PROGRESS.md](docs/PROGRESS.md) và [docs/WORK_LOG.md](docs/WORK_LOG.md).

## 3. Dữ liệu

| Bộ dữ liệu | Vai trò trong project | Quy mô liên quan |
|---|---|---:|
| BKAI Legal Retrieval | Corpus subset dùng để chạy baseline G0 | 5.000 văn bản |
| YuITC Vietnamese Legal Documents | Query và qrels để đánh giá baseline G0 | Chuẩn bị 500 query; lần đánh giá ghi nhận dùng 100 query |
| Zalo AI Legal Text Retrieval 2021 | Benchmark chính đã khóa ở G1 | 61.425 văn bản; 3.196 query; 2.556 qrels train và 640 qrels test |

Subset G0 được chọn có chủ đích để giữ các tài liệu liên quan trước khi bổ sung tài liệu cho đủ quy mô. Do đó, metric G0 chỉ mô tả lần chạy trên subset này, không đại diện cho toàn bộ BKAI/YuITC hoặc benchmark Zalo. Các revision, thống kê split và checksum được ghi trong manifest của project.

## 4. Pipeline baseline G0 đã chạy

Sơ đồ dưới đây mô tả đúng luồng G0: corpus được chuẩn bị để tìm kiếm; câu hỏi được đưa vào các baseline; mỗi baseline trả danh sách xếp hạng. Với câu hỏi minh họa, danh sách được xem trực tiếp dưới dạng Top-5. Với query có qrels, evaluator đối chiếu dự đoán và nhãn liên quan để tính metric.

**Cách hiểu các khối:** corpus là kho văn bản cần tìm; query là câu hỏi; index là cấu trúc giúp tìm trong kho; mỗi baseline chấm và sắp tài liệu theo thứ tự riêng; Top-K là các kết quả đầu để đọc kiểm tra; qrels là nhãn liên quan dùng để chấm metric. Điểm giữa Boolean, TF-IDF và BM25 có thang đo khác nhau nên không so sánh trực tiếp độ lớn score giữa các phương pháp.

Trong lần G0, ba phương pháp được gọi từ repository tham khảo Daijestic tại revision `92fc24310adf26fd401573003028689e5cacc289`. Đây là baseline tham khảo đã tích hợp và chạy trong project, không phải các thuật toán do project tự xây dựng từ đầu.

Người dùng xác nhận đã tự vẽ và giải thích sơ đồ pipeline theo yêu cầu G0.4. Sơ đồ trong repository là tài liệu hỗ trợ để đối chiếu nội dung.


## 5. Cách cài đặt và chạy baseline

Các lệnh sau chạy bằng PowerShell tại thư mục gốc project `legal_ir`. Cần có Python 3.10 và dữ liệu BKAI/YuITC khả dụng trong cache hoặc theo cấu hình chuẩn bị dữ liệu.

### 5.1. Cài môi trường

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 5.2. Lấy đúng phiên bản mã baseline tham khảo

Thực hiện một lần nếu thư mục sibling `..\references\vietnamese-legal-ir` chưa tồn tại:

```powershell
New-Item -ItemType Directory -Force ..\references | Out-Null
git clone https://github.com/Daijestic/vietnamese-legal-ir.git ..\references\vietnamese-legal-ir
git -C ..\references\vietnamese-legal-ir checkout 92fc24310adf26fd401573003028689e5cacc289
```

### 5.3. Chuẩn bị dữ liệu, tính metric và xem Top-K

```powershell
python -m src.data.prepare --max-docs 5000 --max-queries 500
python -m src.evaluation.run_baselines --max-queries 100 --top-k 10
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

Lệnh thứ nhất chuẩn bị subset và manifest; lệnh thứ hai chạy đánh giá trên 100 query; lệnh thứ ba chạy các câu hỏi thủ công và lưu kết quả Top-5. Project lưu metric/cấu hình/log trong `outputs/reports/baseline_g0/`, predictions trong `outputs/predictions/`. Các đầu ra này có thể tái tạo bằng cách chạy lại lệnh trong cùng môi trường, cùng dữ liệu và revision tham khảo.

## 6. Kết quả baseline G0

Metric ghi nhận trên 100 query YuITC của subset G0:

| Phương pháp | Số query | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|---:|
| Boolean | 100 | 0,2050 | 0,1912 | 0,1960 |
| TF-IDF | 100 | 0,8800 | 0,7394 | 0,7795 |
| BM25 | 100 | 0,9450 | 0,8485 | 0,8767 |

Trong lần chạy này, BM25 có metric cao nhất trong ba baseline. Đây là kết quả trên subset được mô tả ở trên; không đủ căn cứ để khẳng định BM25 sẽ tốt hơn trên benchmark Zalo.

### Truy vấn thật và kết quả Top-5

Lệnh đã dùng để tạo log và CSV minh chứng cho truy vấn này:

```powershell
python -m src.app.query --query "Điều kiện đăng ký kết hôn được pháp luật quy định như thế nào?" --top-k 5 --output docs/evidence/g0_topk_results.csv
```

**Câu hỏi:** “Điều kiện đăng ký kết hôn được pháp luật quy định như thế nào?”

Ví dụ kết quả BM25 được ghi từ lần chạy thật:

| Hạng | ID văn bản | BM25 score |
|---:|---:|---:|
| 1 | 908 | 20,200013 |
| 2 | 47569 | 19,698886 |
| 3 | 4579 | 18,910132 |
| 4 | 3131 | 18,567562 |
| 5 | 61763 | 18,397847 |

Log có kết quả Top-5 riêng cho Boolean, TF-IDF và BM25; CSV tương ứng lưu 15 dòng xếp hạng gồm query, phương pháp, ID, rank, score và snippet. Mở [log truy vấn](docs/evidence/g0_topk_terminal.log) hoặc [CSV Top-K](docs/evidence/g0_topk_results.csv) để kiểm tra đầu ra chi tiết.

## 7. Kết quả khóa dữ liệu G1

Benchmark Zalo đã được chuẩn hóa và xác minh trước khi dùng cho thí nghiệm retrieval:

- Corpus: 61.425 văn bản; query: 3.196.
- Qrels train chính thức: 2.556; chia xác định thành 2.300 train và 256 validation; giữ nguyên 640 query test.
- Manifest lưu phiên bản nguồn, split, checksum, schema và số lượng dữ liệu.
- Evaluator hỗ trợ Recall@10, Recall@50, MRR, MAP và nDCG@10.
- Lệnh xác minh đã chạy thành công:

```powershell
python -m src.data.prepare_g1 --verify
```

Kết quả lệnh: `G1 lock verified`; xác minh 6 artifact đã xử lý và 7 artifact nguồn. G1 xác nhận benchmark/evaluator; kết quả retrieval BM25 Zalo thuộc thí nghiệm G2 bên dưới.

## 8. Kết quả BM25 B0 trên Zalo (G2)

BM25 tham khảo Daijestic tại revision `92fc24310adf26fd401573003028689e5cacc289` được fit trên toàn corpus Zalo. Validation có 256 query; mỗi run lưu tối đa 100 kết quả. Grid `k1={1.2,1.5,1.8}`, `b={0.5,0.75,1.0}` được chọn hoàn toàn bằng nDCG@10 trên validation.

| Cấu hình | k1 | b | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mặc định | 1.5 | 0.75 | 0.8594 | 0.9492 | 0.6185 | 0.6185 | 0.6725 |
| Chọn trên validation | 1.2 | 0.75 | 0.8555 | 0.9492 | 0.6231 | 0.6231 | 0.6751 |

Cấu hình chọn tăng nhẹ nDCG@10, MAP và MRR, nhưng giảm Recall@10. Đây là kết quả trên validation của 256 query, chưa chứng minh khác biệt có ý nghĩa thống kê hoặc tốt hơn trên test. Latency chi tiết và kết quả các cấu hình khác nằm trong `outputs/bm25_zalo_validation_20261028/metrics_comparison.csv`.

Index 91.617.306 byte, predictions cho 9 cấu hình, metric theo query, config/checksum, log và đánh giá CLI độc lập được lưu tại `outputs/bm25_zalo_validation_20261028/`. Replay từ index tạo lại byte-for-byte cả 9 prediction files và cùng metric. Lệnh:

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.run_bm25 --top-k 100 --output-dir outputs\bm25_zalo_validation_20261028
.\.venv\Scripts\python.exe -m src.evaluation.run_bm25 --top-k 100 --reuse-index outputs\bm25_zalo_validation_20261028\bm25_index.pkl --output-dir outputs\bm25_zalo_validation_20261028
```

## 9. Tệp minh chứng trong repository

| Minh chứng | Tệp |
|---|---|
| Log truy vấn Top-5 thật | [`docs/evidence/g0_topk_terminal.log`](docs/evidence/g0_topk_terminal.log) |
| CSV kết quả của truy vấn trong log | [`docs/evidence/g0_topk_results.csv`](docs/evidence/g0_topk_results.csv) |
| Báo cáo metric G0 | `outputs/reports/baseline_g0/evaluation_report.csv` |
| Cấu hình/checksum lần chạy G0 | `outputs/reports/baseline_g0/run_config.json` |
| Manifest benchmark Zalo | `data/processed/benchmarks/zalo_2021/manifest.json` |
| Tiến độ theo tuần/Gate | [`docs/PROGRESS.md`](docs/PROGRESS.md) |
| Metric/predictions/config/log của G2 | `outputs/bm25_zalo_validation_20261028/` |

### Giới hạn cần nêu khi báo cáo

1. Metric G0 được tính trên subset BKAI/YuITC có chọn lọc, không phải toàn bộ benchmark.
2. Mã Boolean, TF-IDF và BM25 ở G0 được gọi từ repository tham khảo đã pin revision.
3. G2 chỉ đánh giá validation; test vẫn để dành cho đánh giá cuối sau khi chốt phương pháp.
4. Kết quả hiện có chứng minh BM25 B0 đã chạy; chưa có bằng chứng dense retrieval, fusion hay reranker cải thiện chất lượng.

## 10. Các mốc tiếp theo

Các mốc sau G2 chưa hoàn thành; đây là công việc theo lộ trình, không phải kết quả hiện tại. Trạng thái, giới hạn và bước tiếp theo được ghi tại [docs/PROGRESS.md](docs/PROGRESS.md) và [docs/WORK_LOG.md](docs/WORK_LOG.md).
