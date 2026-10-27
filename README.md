# Truy xuất văn bản pháp luật tiếng Việt

## Mục tiêu

Đồ án xây dựng hệ thống truy xuất và xếp hạng văn bản pháp luật tiếng Việt theo câu hỏi tự nhiên. Luồng nghiên cứu dự kiến gồm truy xuất từ khóa, truy xuất ngữ nghĩa, kết hợp kết quả và tái xếp hạng. Sản phẩm phải trả về văn bản liên quan có nguồn; trọng tâm đánh giá là chất lượng xếp hạng, không phải sinh câu trả lời tư vấn pháp lý.

## Tiến độ và quyết định hiện tại

| Mốc | Yêu cầu | Trạng thái | Bằng chứng chính |
|---|---|---|---|
| G0 / Tuần 1 | Dựng baseline chạy được, xem Top-K và tính metric trên dữ liệu công khai | Đạt có giới hạn | Baseline Boolean, TF-IDF, BM25 và Top-5 trên subset BKAI/YuITC; xem `docs/g0_acceptance.md` |
| G1 / Tuần 2 | Phân tích, chuẩn hóa và khóa benchmark cùng evaluator | Đạt | Zalo đã khóa, có manifest/checksum, split và evaluator; xem `docs/g1_data_lock.md` |
| G2 / Tuần 3 | Xây BM25 trên Zalo, tạo predictions và báo cáo validation | Chưa thực hiện | Đây là công việc kế tiếp |

**Được chuyển sang thực hiện G2. Chưa có BM25 benchmark trên Zalo.** Các số G0 chỉ là bằng chứng tích hợp trên tập con chẩn đoán; không dùng chúng như kết quả Zalo hay kết luận so sánh cuối cùng.

## Phạm vi dữ liệu

| Bộ dữ liệu | Vai trò | Trạng thái |
|---|---|---|
| BKAI corpus + YuITC queries/qrels | Tập con để kiểm tra pipeline G0 | Đã chạy trên 5.000 tài liệu, 500 truy vấn chuẩn bị; metric tính trên 100 truy vấn |
| Zalo AI Legal Text Retrieval 2021 | Benchmark chính của đồ án | Đã khóa 61.425 tài liệu, 3.196 truy vấn; train/validation/test lần lượt 2.300/256/640 truy vấn |
| YuITC đầy đủ | Phân tích bổ sung | Không dùng làm benchmark độc lập sạch vì có 726 nhóm truy vấn trùng nguyên văn giữa train/test |

Qrel của benchmark là nguồn nhãn liên quan. Truy vấn tự soạn chỉ dùng kiểm tra Top-K thủ công; không thêm vào qrel. Không dùng dữ liệu test để chọn tham số hoặc mô hình.

## Kết quả G0

G0 dùng subset được chọn có chủ đích để giữ CID liên quan của các truy vấn đã chọn rồi bổ sung tài liệu cho đủ 5.000. Vì vậy đây là kiểm tra đường chạy, không phải ước lượng đại diện cho toàn bộ corpus.

| Phương pháp tham khảo | Truy vấn được chấm | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|---:|
| Boolean | 100 | 0.2050 | 0.1912 | 0.1960 |
| TF-IDF | 100 | 0.8800 | 0.7394 | 0.7795 |
| BM25 | 100 | 0.9450 | 0.8485 | 0.8767 |

Top-5 của 10 truy vấn thủ công được lưu trong `outputs/predictions/manual_top5.csv`; ví dụ và diễn giải tại `docs/g0_topk_evidence.md`. Báo cáo đầy đủ, cấu hình và log ở `outputs/reports/baseline_g0/` và `outputs/predictions/baseline_g0/`.

## G1: benchmark và quy trình đánh giá

Zalo được cố định theo revision ghi trong `data/processed/benchmarks/zalo_2021/manifest.json`. Các tệp chuẩn hóa gồm corpus, queries, qrels train/validation/test và split; manifest chứa checksum nguồn và đầu ra. Có báo cáo thống kê, kiểm tra tính toàn vẹn, notebook phân tích đã chạy và evaluator cho Recall@10/50, MRR, MAP, nDCG@10. Bảy kiểm thử evaluator đã đạt.

G1 chỉ khóa dữ liệu và cách đánh giá; không chạy retrieval trên Zalo. Thống kê chi tiết nằm trong `outputs/reports/g1_data_lock/dataset_report.md`.

## Công việc kế tiếp: G2 – BM25

1. Xác minh dữ liệu khóa bằng `python -m src.data.prepare_g1 --verify`.
2. Chạy runner BM25 với tokenizer, tiền xử lý và tham số mặc định được ghi trong cấu hình lần chạy.
3. Tạo danh sách xếp hạng Top-100 trên validation theo schema `qid,doc_id,rank,score`.
4. Chấm bằng evaluator G1 và lưu predictions, cấu hình chạy, log và metric.
5. Chọn thiết lập chỉ bằng train/validation; để dành qrel test cho đánh giá cuối sau khi cố định phương pháp.

Từ PowerShell tại thư mục `legal_ir`:

```powershell
python -m src.data.prepare_g1 --verify
python -u -m src.evaluation.run_g2_bm25 --top-k 100
python -m src.evaluation.evaluate_runs `
  --qrels data/processed/benchmarks/zalo_2021/qrels_validation.jsonl `
  --run outputs/g2_bm25/bm25_validation_run.csv `
  --corpus data/processed/benchmarks/zalo_2021/corpus.jsonl `
  --output outputs/g2_bm25/evaluation.json
```

Runner dùng `k1=1.5`, `b=0.75` và bộ tách từ `underthesea` của checkout Daijestic đã pin. Có thể truyền `--k1`, `--b`, `--top-k` để tạo cấu hình khác; chỉ chọn cấu hình bằng validation. Lần chạy đầy đủ cần lập chỉ mục trên 61.425 tài liệu, nên bước này có thể mất nhiều phút trên CPU.

Các đầu ra được ghi ở `outputs/g2_bm25/`: `bm25_validation_run.csv`, `run_config.json`, `run.log`, `evaluation.json` và `evaluation_per_query.csv`. Báo cáo JSON chứa metric trung bình; CSV per-query giúp xem từng câu. G1/test không bị ghi đè.

Gate G2 chỉ được nghiệm thu khi có BM25 chạy trên Zalo validation, tệp predictions và báo cáo có thể tái tạo. Sau đó mới chuyển sang dense retrieval theo lịch tuần 4.

## Cấu trúc hiện có

```text
configs/                         cấu hình và truy vấn thủ công
data/processed/benchmarks/       dữ liệu benchmark đã khóa (không đưa vào Git)
docs/                            nghiệm thu, pipeline và tái lập
notebooks/                       phân tích dữ liệu
outputs/predictions/             thứ hạng và kết quả truy vấn (không đưa vào Git)
outputs/reports/                 metric và báo cáo
src/app/query.py                 truy vấn CLI cho luồng G0
src/data/                        chuẩn bị G0 và khóa dữ liệu G1
src/evaluation/                  runner G0 và evaluator G1
src/retrieval/                   thư mục mã truy xuất hiện có (BM25 G2 chưa tích hợp)
tests/                           kiểm thử metric và evaluator G1
references/                      kho mã tham khảo, tách khỏi sản phẩm
```

Cây trên mô tả hiện trạng, không phải toàn bộ kiến trúc đích. Dense/FAISS, fusion, reranker, API/Web và thí nghiệm B0–B4 chưa được triển khai.

## Tái lập các mốc đã hoàn thành

Các lệnh dưới đây ghi lại quy trình đã dùng. Muốn chạy lại G0 cần có cache/archive BKAI và YuITC cùng checkout mã tham khảo Daijestic theo revision trong `docs/reproducibility/source_manifest.json`.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.data.prepare --max-docs 5000 --max-queries 500
python -m src.evaluation.run_baselines --max-queries 100 --top-k 10
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

G1 đã được chuẩn bị và xác minh theo nhật ký `docs/reproducibility/setup-log.md`. Để chỉ xác minh checksum mà không tạo lại dữ liệu, chạy `python -m src.data.prepare_g1 --verify`. Không dùng `--force` trừ khi chủ động tái tạo benchmark.

## Tài liệu

- `docs/g0_acceptance.md`: nghiệm thu G0, bằng chứng và giới hạn.
- `docs/g0_topk_evidence.md`: ví dụ truy vấn Top-5 thực tế.
- `docs/g1_data_lock.md`: quyết định khóa benchmark và evaluator.
- `docs/g2_bm25.md`: hướng dẫn chạy và nghiệm thu BM25 trên Zalo validation.
- `docs/pipeline.md`: luồng đã chạy và kiến trúc tham khảo.
- `docs/reproducibility/setup-log.md`: môi trường và nhật ký thao tác.
