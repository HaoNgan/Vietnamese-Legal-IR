# Báo cáo dữ liệu benchmark G1

## Kết luận sử dụng

Zalo AI Legal Text Retrieval 2021 được khóa làm benchmark chính. Bản dữ liệu cục bộ ở revision `5fb3df4300b3a81455fe09af444ec159afa8d212` đã được chuẩn hóa, chia split xác định, kiểm tra tính toàn vẹn và ghi checksum. **Báo cáo này mô tả dữ liệu; không có kết quả retrieval và không nghiệm thu BM25 G2.**

## Quy mô và split

| Phần | Query | Qrel | Vai trò |
|---|---:|---:|---|
| Corpus | — | — | 61.425 tài liệu |
| Train | 2.300 | 2.300 | Phát triển |
| Validation | 256 | 256 | Chọn phương pháp/tham số |
| Test chính thức | 640 | 640 | Chỉ đánh giá cuối sau khi cố định hệ thống |

Nguồn chính thức có 2.556 dòng train qrel và 640 dòng test qrel. 256 query validation được tách xác định từ train; test chính thức không bị chia lại. Cấu hình/seed và chi tiết checksum nằm trong `manifest.json` cùng `configs/g1_data_lock.json`.

## Schema

Nguồn Zalo dùng `id/title/text` cho corpus, `query_id/question` cho query và `query_id/corpus_id/score` cho qrel. Schema chuẩn sau xử lý là:

- Corpus: `doc_id,title,text`
- Query: `qid,query`
- Qrel: `qid,doc_id,relevance`

ID và nhãn được giữ nguyên; văn bản chuẩn hóa Unicode NFC và khoảng trắng. Tài liệu rỗng hoặc có nội dung trùng được giữ lại.

## Kiểm tra toàn vẹn

| Kiểm tra | Kết quả |
|---|---:|
| ID corpus trùng | 0 |
| ID query trùng | 0 |
| Query trùng sau chuẩn hóa | 0 |
| Cặp qrel trùng | 0 |
| Qrel trỏ tới tài liệu không có trong corpus | 0 |
| Query không có qrel | 0 |
| ID query giao giữa train và test | 0 |
| Query trùng nguyên văn giữa split sau chuẩn hóa | 0 |
| Tài liệu không có văn bản được giữ | 357 |
| Dòng tài liệu trùng văn bản sau chuẩn hóa được giữ | 1.277 |

Kiểm tra query chỉ phát hiện trùng chính xác sau chuẩn hóa, không chứng minh không có paraphrase hoặc gần trùng ngữ nghĩa. Qrel test nằm trong bản sao cục bộ nhưng không được dùng chọn mô hình/tham số.

## Phân bố độ dài Zalo

Số từ được tính bằng cách tách theo khoảng trắng, chỉ dùng mô tả.

| Trường | Min | P25 | Trung vị | Trung bình | P75 | P90 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Từ trên tài liệu | 0 | 97 | 183 | 287.8692 | 345 | 592 | 815 | 1.666 | 55.368 |
| Từ trên query | 4 | 15 | 19 | 19.0488 | 23 | 27 | 30 | 34 | 44 |
| Ký tự trên query | 16 | 64 | 83 | 84.8611 | 104 | 123 | 133 | 152 | 187 |
| Tài liệu liên quan/query | 1 | 1 | 1 | 1.0 | 1 | 1 | 1 | 1 | 1 |

## Phân tích bổ sung YuITC/BKAI

YuITC được phân tích riêng, không nhập vào benchmark Zalo. Train có 89.261 dòng query/qrel record và 99.698 dòng qrel; test có 29.746 record và 33.299 dòng qrel. BKAI có 261.597 CID tài liệu; 68.663 CID liên quan duy nhất trong YuITC đều có trong corpus BKAI.

Có 726 nhóm văn bản query trùng nguyên văn sau chuẩn hóa giữa train và test YuITC. Do đó không xem split YuITC là phép kiểm tra độc lập sạch; dữ liệu gốc được giữ nguyên.

## Manifest và đầu ra

Manifest `manifest.json` ghi revision nguồn, SHA-256 của nguồn và các tệp đã xử lý, schema, số lượng, split, seed và giao thức metric. Dataset đã chuẩn hóa nằm trong `data/processed/benchmarks/zalo_2021/`; báo cáo JSON và biểu đồ nằm cạnh báo cáo Markdown này.

Evaluator G1 hỗ trợ Recall@10, Recall@50, MRR, MAP và nDCG@10. Đây là định nghĩa/giao thức đánh giá đã khóa, không phải điểm hiệu năng. MAP/MRR phụ thuộc độ sâu run và các phương pháp phải được chấm ở độ sâu tương đương.
