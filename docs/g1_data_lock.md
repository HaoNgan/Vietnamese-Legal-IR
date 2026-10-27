# Nghiệm thu G1 tuần 2

## Kết luận

**G1 đạt yêu cầu khóa benchmark và evaluator.** Dataset Zalo đã được cố định phiên bản, chuẩn hóa schema, chia train/validation/test xác định, kiểm tra toàn vẹn, ghi checksum và tạo báo cáo phân tích. Bộ evaluator đã triển khai và qua 7 kiểm thử.

G1 **không** bao gồm chạy BM25 trên Zalo. Không có kết quả retrieval Zalo trong hồ sơ mốc này; đó là nhiệm vụ G2/tuần 3.

## Benchmark chính và split

Benchmark chính là Zalo AI Legal Text Retrieval 2021, nguồn `minhnguyent546/zalo-ai-legal-text-retrieval-2021`, revision `5fb3df4300b3a81455fe09af444ec159afa8d212`. YuITC/BKAI được giữ riêng làm dữ liệu phân tích bổ sung và tập con G0.

| Phần | Số lượng | Vai trò |
|---|---:|---|
| Corpus Zalo | 61.425 tài liệu | Corpus dùng chung cho truy xuất |
| Train | 2.300 query/qrel | Phát triển phương pháp |
| Validation | 256 query/qrel | Chọn tham số và phương pháp |
| Test chính thức | 640 query/qrel | Chỉ đánh giá cuối cùng sau khi cố định hệ thống |

Tập validation được tách xác định từ 10% query train theo thứ tự SHA-256 với seed `zalo-g1-v1`; tập test chính thức được giữ nguyên. Qrel test có trong bản sao cục bộ nhưng không được dùng để tinh chỉnh hay chọn cấu hình.

## Schema chuẩn

| Tệp logic | Trường |
|---|---|
| Corpus | `doc_id,title,text` |
| Query | `qid,query` |
| Qrel | `qid,doc_id,relevance` |
| Run/predictions | `qid,doc_id,rank` và `score` tùy chọn |

ID và nhãn relevance được giữ nguyên. Văn bản được chuẩn hóa Unicode NFC và khoảng trắng. Tài liệu rỗng hoặc trùng nội dung vẫn được giữ; xử lý lọc sau này phải là một phiên bản/thí nghiệm có ghi nhận, không sửa âm thầm benchmark khóa.

## Kiểm tra toàn vẹn và giới hạn dữ liệu

Trong bản dữ liệu đã khóa: không có ID corpus/query trùng, cặp qrel trùng, query trùng nguyên văn sau chuẩn hóa, qrel trỏ tới ID thiếu trong corpus, query thiếu qrel hay query ID giao giữa train và test. Có 357 tài liệu rỗng và 1.277 dòng có văn bản trùng chuẩn hóa; các dòng được giữ nguyên.

Kiểm tra chồng lấn query chỉ so khớp chính xác sau chuẩn hóa; chưa đánh giá đầy đủ paraphrase/gần trùng về ngữ nghĩa. Bản mirror và revision được dùng có ghi trong manifest; không diễn giải điều này thành xác minh độc lập với mọi bản phát hành khác.

YuITC có 726 nhóm query trùng văn bản chính xác giữa split train/test. Vì vậy YuITC chỉ dùng phân tích bổ sung, không được trình bày là benchmark đánh giá độc lập sạch.

## Quy trình metric đã khóa

Evaluator tại `src/evaluation/` tính macro-average trên toàn bộ qid trong qrel của split được chọn; query không có prediction được tính như danh sách rỗng. Chương trình kiểm tra qid/doc_id/rank và các dòng trùng/lỗi.

| Metric | Sử dụng |
|---|---|
| Recall@10, Recall@50 | Độ bao phủ ứng viên |
| MRR | Vị trí kết quả liên quan đầu tiên |
| MAP | Precision trung bình theo thứ hạng |
| nDCG@10 | Chất lượng thứ tự trong top 10 |

MAP và MRR phụ thuộc độ sâu run; mọi phương pháp so sánh phải dùng cùng độ sâu và báo cáo độ sâu. Bảy kiểm thử đã đạt để xác minh phần triển khai evaluator; đây không phải kết quả benchmark retrieval.

## Bằng chứng đầu ra

- Dữ liệu chuẩn hóa và split: `data/processed/benchmarks/zalo_2021/`.
- Checksum nguồn/đầu ra và split: `data/processed/benchmarks/zalo_2021/manifest.json`.
- Cấu hình: `configs/g1_data_lock.json`.
- Báo cáo thống kê: `outputs/reports/g1_data_lock/dataset_report.md` và `.json`.
- Notebook đã chạy và biểu đồ: `outputs/reports/g1_data_lock/01_dataset_analysis.executed.ipynb`, `zalo_distributions.png`.
- Nhật ký các lệnh và môi trường: `docs/reproducibility/setup-log.md`.

## Xác minh hoặc tái tạo dữ liệu

Để kiểm tra checksum mà không ghi lại dữ liệu:

```powershell
python -m src.data.prepare_g1 --verify
```

Lệnh tạo mới lần đầu (cần cache nguồn đã pin):

```powershell
python -m src.data.prepare_g1
```

Chỉ dùng `--force` khi chủ động tái tạo benchmark và đã xử lý phiên bản dữ liệu hiện có. Các lệnh trên chỉ chuẩn bị/kiểm tra dữ liệu, không chạy retrieval.

Để chấm một run sau này, truyền qrels validation, ranked CSV và corpus đã khóa vào evaluator. Không thay qrels validation bằng qrels test trong quá trình phát triển.

## Việc kế tiếp: G2 – BM25

1. Chạy `prepare_g1 --verify` và xác nhận manifest không đổi.
2. Triển khai BM25 trong project chính, ghi tokenizer/tiền xử lý/tham số.
3. Sinh ranking cho 256 query validation theo schema run đã nêu.
4. Chạy evaluator và lưu metric, predictions, cấu hình, log.
5. Chọn cấu hình bằng validation; giữ test đến khi phương pháp được cố định.

Chỉ nghiệm thu G2 khi BM25 trên Zalo validation có thể tái tạo từ cấu hình và prediction file. G1 chưa có kết quả nào đáp ứng tiêu chí đó.
