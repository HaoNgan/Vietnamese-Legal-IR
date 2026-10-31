# Kết quả truy vấn thủ công Top-5 · G0.1

## Mục đích và nguồn

Tài liệu này ghi hai dạng bằng chứng đầu ra thật của baseline G0: 10 truy vấn thủ công đã lưu lâu hơn và một lần truy vấn terminal được ghi trực tiếp vào log. Log minh chứng mới nhất nằm tại `evidence/g0_topk_terminal.log`; ranked CSV của đúng lần chạy đó là `evidence/g0_topk_results.csv`. Dữ liệu 10 truy vấn nằm trong `../outputs/predictions/manual_top5.csv`, được tạo bởi lệnh:

```powershell
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

Mười câu hỏi tự soạn được chạy qua Boolean, TF-IDF và BM25. CSV lưu query, phương pháp, ID tài liệu, hạng, score và excerpt; cấu hình lần chạy ở `../outputs/predictions/manual_top5_config.json`. BM25 và TF-IDF đều có đủ Top-5 cho 10 câu hỏi. Boolean có kết quả cho 3 trong 10 câu; vì vậy CSV có 115 dòng kết quả thay vì 150. Đây vẫn là 10 truy vấn có Top-5 từ ít nhất một phương pháp, nhưng không phải cả ba phương pháp đều trả kết quả cho mọi câu.

## Ví dụ truy vấn

> Điều kiện đăng ký kết hôn được pháp luật quy định như thế nào?

| Phương pháp | Hạng | ID tài liệu | Score |
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

## Cách diễn giải

Đây là kết quả trả về thật của lần chạy đã lưu. Mỗi phương pháp tự xếp kết quả theo score của nó; score Boolean, TF-IDF và BM25 không cùng thang đo nên không so sánh trực tiếp các con số giữa các phương pháp. Ví dụ này cho thấy Top-K đầu ra có thể được quan sát; nó không thay thế metric trên qrels và không chứng minh độ chính xác tổng quát.

Log `evidence/g0_topk_terminal.log` ghi lệnh đã chạy, câu hỏi, kết quả Boolean/TF-IDF/BM25 và exit code 0. CSV cạnh log lưu đủ 15 dòng xếp hạng để kiểm tra ID, score và excerpt. Như vậy đã có log truy vấn thật theo yêu cầu G0.1; nếu cần trình chiếu trực quan, có thể mở file log hoặc CSV.
