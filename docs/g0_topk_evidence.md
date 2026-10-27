# Bằng chứng truy vấn Top-5 G0.1

## Nguồn kết quả

Kết quả được trích từ `outputs/predictions/manual_top5.csv`, đầu ra của lệnh:

```powershell
python -m src.app.query --query-file configs/g0_manual_queries.txt --top-k 5
```

Tệp chứa 10 query thủ công chạy qua Boolean, TF-IDF và BM25, cùng ID tài liệu, thứ hạng, score và excerpt. Cấu hình nằm tại `outputs/predictions/manual_top5_config.json`.

## Ví dụ: truy vấn điều kiện đăng ký kết hôn

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

Các ID và điểm trên là output truy vấn thực. Không diễn giải chênh lệch score giữa các phương pháp như cùng một thang đo. Đây là bằng chứng hệ thống trả kết quả và hỗ trợ quan sát thủ công, không phải metric benchmark hay kết luận phương pháp nào tốt hơn.
