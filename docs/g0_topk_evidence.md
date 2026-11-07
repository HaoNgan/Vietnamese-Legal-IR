# Ví dụ kết quả truy vấn Top-5 của G0

## Mục đích

File này giúp xem trực tiếp một câu hỏi và các văn bản được Boolean, TF-IDF, BM25 xếp hạng. Đây là ví dụ đầu ra, không thay thế việc đánh giá bằng qrels.

## Chạy lại truy vấn mẫu

Mười câu hỏi mẫu được lưu trong `configs/g0_manual_queries.txt`. Chạy từ thư mục gốc dự án:

```powershell
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

Kết quả của 10 câu hỏi nằm trong `outputs/predictions/manual_top5.csv`; cấu hình chạy nằm cạnh đó trong `manual_top5_config.json`.

Trong lần chạy đã lưu, TF-IDF và BM25 trả đủ 5 kết quả cho cả 10 câu hỏi. Boolean trả kết quả cho 3 câu hỏi. Vì vậy CSV có 115 dòng kết quả, không phải 150.

## Ví dụ

**Câu hỏi:** Điều kiện đăng ký kết hôn được pháp luật quy định như thế nào?

| Phương pháp | Hạng | ID tài liệu | Điểm xếp hạng |
|---|---:|---:|---:|
| Boolean | 1 | 2263 | 5.0 |
| Boolean | 2 | 2272 | 5.0 |
| Boolean | 3 | 2275 | 5.0 |
| Boolean | 4 | 47569 | 5.0 |
| Boolean | 5 | 907 | 5.0 |
| TF-IDF | 1 | 47569 | 0.708048 |
| TF-IDF | 2 | 3131 | 0.663221 |
| TF-IDF | 3 | 4564 | 0.654209 |
| TF-IDF | 4 | 908 | 0.626784 |
| TF-IDF | 5 | 4585 | 0.623494 |
| BM25 | 1 | 908 | 20.200013 |
| BM25 | 2 | 47569 | 19.698887 |
| BM25 | 3 | 4579 | 18.910132 |
| BM25 | 4 | 3131 | 18.567563 |
| BM25 | 5 | 61763 | 18.397848 |

Điểm của từng phương pháp có thang đo riêng. Chỉ dùng điểm để xếp hạng trong cùng một phương pháp; không so trực tiếp điểm Boolean với TF-IDF hoặc BM25.

## Bằng chứng lưu trong dự án

- `docs/evidence/g0_topk_terminal.log`: lệnh đã chạy, câu hỏi, kết quả hiển thị trong terminal và exit code 0.
- `docs/evidence/g0_topk_results.csv`: 15 kết quả Top-5 của câu hỏi trong log, gồm ID, hạng, điểm và đoạn trích.
- `outputs/predictions/manual_top5.csv`: kết quả của 10 câu hỏi mẫu qua cả ba phương pháp.
