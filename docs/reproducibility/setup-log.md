# Nhật ký môi trường và tái lập

## Phạm vi

Đây là nhật ký các lần chuẩn bị G0 và khóa dữ liệu G1 đã được ghi nhận. Các lệnh lịch sử không đồng nghĩa đã chạy lại trong lần sửa tài liệu này. Phiên bản package đầy đủ nằm trong `pip-freeze.txt`; nguồn và revision tham khảo nằm trong `source_manifest.json`.

## Môi trường được ghi nhận

- Ngày chạy G0/G1: 2026-10-20, Asia/Saigon.
- Hệ điều hành: Windows; lệnh PowerShell.
- Python: 3.10.0 trong `legal_ir\\.venv`; môi trường không dùng system site packages.
- pip: 21.2.3 tại thời điểm kiểm tra.
- Các package chính gồm `pyarrow`, `underthesea` và `matplotlib`; toàn bộ danh sách ở `pip-freeze.txt`.
- Dataset được đọc từ cache Hugging Face cục bộ, với revision/checksum đã ghi trong manifest. Cache không nằm trong repo.

## G0 đã chạy

Lệnh chuẩn bị 5.000 tài liệu BKAI và 500 query/qrel YuITC; qrel được giữ nguyên và 558 CID liên quan duy nhất đều có trong subset. Sau đó chạy baseline trên 100 query và tạo Top-5 thủ công cho 10 query:

```powershell
python -m src.data.prepare --max-docs 5000 --max-queries 500
python -m src.evaluation.run_baselines --max-queries 100 --top-k 10
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

Kết quả được lưu ở `outputs/reports/baseline_g0/` và `outputs/predictions/`. Đây là subset chẩn đoán; chi tiết và giới hạn tại `docs/g0_acceptance.md`.

## G1 đã chạy

Nguồn Zalo/YuITC/BKAI được cố định theo revision đã pin. Lần chạy thành công của G1 dùng Python trong virtual environment của repo; lần chạy trước bằng Python toàn cục dừng do thiếu `pyarrow`, sau đó đã chạy lại bằng đúng interpreter.

Các thao tác đã ghi nhận:

1. Chạy `python -m src.data.prepare_g1 --force` để tạo dữ liệu chuẩn hóa và báo cáo G1. Cờ `--force` chỉ được dùng khi làm mới gói G1 sau bổ sung checksum; không tác động đầu ra G0.
2. Chạy `python -m unittest discover -s tests -v`; cả 7 kiểm thử evaluator đạt.
3. Chạy `python -m src.data.prepare_g1 --verify`; 6 tệp đã xử lý, 7 tệp nguồn và checksum cấu hình khớp manifest, không ghi lại dữ liệu.
4. Thực thi notebook phân tích Zalo; lần chạy hoàn tất 5 ô. Có cảnh báo Proactor/ZMQ và quyền hồ sơ IPython, nhưng không có ô thất bại trong lần chạy thành công.

Không chạy retrieval nào trên Zalo trong G1. Do đó chưa có metric BM25 Zalo.

## Trạng thái Git

Hồ sơ lần chạy ghi kho mã chính chưa có commit; remote/push cũng chưa được xác nhận. Vì vậy G0.3 chỉ được ghi nhận một phần cho tới khi repository cá nhân được commit và, nếu yêu cầu nộp bài, remote/push được xác nhận. Không có commit hoặc push nào được thực hiện trong lần chỉnh sửa tài liệu này.

## Bước kế tiếp

G2 là BM25 trên Zalo validation. Trước khi chạy, xác minh dữ liệu:

```powershell
python -m src.data.prepare_g1 --verify
```

Sau đó tạo ranked predictions, chạy evaluator và lưu cấu hình, metric, log. Dùng validation để chọn cấu hình; không dùng test qrels cho tuning. Quy trình nghiệm thu nằm tại `docs/g1_data_lock.md`.
