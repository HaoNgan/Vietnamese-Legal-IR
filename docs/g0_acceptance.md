# Nghiệm thu G0 tuần 1

## Kết luận

**G0 đạt ở phạm vi dựng và kiểm tra baseline trên tập con công khai.** Hệ thống đã chạy Boolean, TF-IDF, BM25, trả kết quả Top-5 cho truy vấn thủ công và tính metric từ qrel. Kết quả chỉ xác nhận đường chạy kỹ thuật; chưa phải phép đo trên benchmark chính Zalo.

G0.3 được đánh giá **đạt một phần**: README, hướng dẫn chạy và `.gitignore` đã có, nhưng hồ sơ dự án ghi kho mã chính chưa có commit và chưa xác nhận remote/push. Đây là việc hoàn tất quản lý repository, không làm mất bằng chứng các lần chạy đã lưu.

## Đối chiếu yêu cầu và bằng chứng

| Yêu cầu | Bằng chứng | Trạng thái | Giới hạn |
|---|---|---|---|
| G0.1 – truy vấn thật trả Top-K | `outputs/predictions/manual_top5.csv`, cấu hình truy vấn; bản đọc nhanh tại `g0_topk_evidence.md` | Đạt | 10 truy vấn thủ công; một số truy vấn Boolean có thể trả ít hơn 5 kết quả |
| G0.2 – baseline và evaluator | `outputs/reports/baseline_g0/evaluation_report.csv`, `run_config.json`, `run.log`; predictions trong `outputs/predictions/baseline_g0/` | Đạt | 100 query trên tập con được chọn có chủ đích |
| G0.3 – README, lệnh chạy và repository | `README.md`, `requirements.txt`, `.gitignore`, `docs/reproducibility/` | Đạt một phần | Chưa có commit/remote được xác nhận theo hồ sơ hiện có |
| G0.4 – hiểu và giải thích pipeline | `docs/pipeline.md` | Đạt | Sơ đồ G0 dựa trên luồng chạy; sơ đồ dense/fusion/rerank là kiến trúc tham khảo, chưa chạy |

## Dữ liệu và cách chạy

G0 dùng corpus BKAI, query/qrel từ YuITC train. Tập chuẩn bị gồm 5.000 tài liệu, 500 query và 566 nhãn qrel (558 CID liên quan duy nhất). Theo manifest lần chuẩn bị, các CID liên quan được giữ trong corpus. Việc đánh giá chấm 100 query đầu theo thứ tự nguồn.

| Phương pháp | Query | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|---:|
| Boolean | 100 | 0.2050 | 0.1912 | 0.1960 |
| TF-IDF | 100 | 0.8800 | 0.7394 | 0.7795 |
| BM25 | 100 | 0.9450 | 0.8485 | 0.8767 |

Subset được tạo để giữ tài liệu liên quan trước khi lấp đủ kích thước. Vì thế các metric trên **không đại diện** cho toàn corpus, không phải kết quả Zalo và không dùng để kết luận tổng quát rằng phương pháp này tốt hơn phương pháp khác.

Mã truy xuất G0 được import từ Daijestic theo revision trong `docs/reproducibility/source_manifest.json`; project chuẩn bị dữ liệu và chạy đánh giá quanh mã tham khảo. Không có dense retrieval, fusion hoặc reranking được thực thi trong G0.

## Hồ sơ bằng chứng

- Top-K thủ công: `configs/g0_manual_queries.txt`, `outputs/predictions/manual_top5.csv`, `outputs/predictions/manual_top5_config.json`.
- Metric, log và cấu hình: `outputs/reports/baseline_g0/`.
- Ranked predictions: `outputs/predictions/baseline_g0/`.
- Môi trường: `docs/reproducibility/setup-log.md`, `docs/reproducibility/pip-freeze.txt`.
- Sơ đồ pipeline: `docs/pipeline.md`.

## Điều kiện tiếp theo

G0 đã chứng minh có thể dựng một hệ thống truy xuất và quan sát kết quả. G1 đã khóa benchmark chính cùng evaluator. Vì vậy bước tiếp theo là **G2/tuần 3 – BM25 trên Zalo validation**, không phải dense retrieval. Cần tạo prediction, metric, cấu hình và log cho lần chạy Zalo trước khi nghiệm thu G2.

## Lệnh đã dùng trong lần chạy G0

Các lệnh được ghi để tái lập; chúng cần cache dữ liệu và checkout mã tham khảo phù hợp.

```powershell
python -m src.data.prepare --max-docs 5000 --max-queries 500
python -m src.evaluation.run_baselines --max-queries 100 --top-k 10
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```
