# Nhật ký công việc đã thực hiện

Đề tài: **Nghiên cứu và xây dựng hệ thống truy xuất văn bản pháp luật tiếng Việt sử dụng mô hình biểu diễn ngữ nghĩa và tái xếp hạng**.

Trang này chỉ ghi việc đã làm và bằng chứng hiện có. Kế hoạch tương lai, hướng dẫn cho AI và nội dung chưa thực hiện không ghi thành kết quả.

## Tuần 1 — G0: baseline ban đầu

- Chuẩn bị subset gồm **5.000 văn bản BKAI** và **500 query/qrel YuITC**.
- Chạy các baseline Boolean, TF-IDF, BM25; phần đánh giá metric dùng **100 query**.
- Chạy truy vấn thủ công để xem Top-K. Artifact gồm report, cấu hình, log, predictions và truy vấn mẫu.
- Các baseline gọi mã tham khảo Daijestic tại revision `92fc24310adf26fd401573003028689e5cacc289`; không phải toàn bộ thuật toán được tự cài trong project.

| Phương pháp | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|
| Boolean | 0.2050 | 0.1911667 | 0.1959823 |
| TF-IDF | 0.8800 | 0.7394127 | 0.7794795 |
| BM25 | 0.9450 | 0.8484980 | 0.8767397 |

**Giới hạn:** đây là subset chọn lọc BKAI/YuITC để kiểm tra baseline, không phải kết quả trên benchmark Zalo và không chứng minh phương pháp nào tốt hơn trên mọi tập.

**Bằng chứng:** `outputs/reports/baseline_g0/`, `outputs/predictions/baseline_g0/`, `outputs/predictions/manual_top5.csv`, `docs/evidence/`. Chi tiết truy vấn mẫu tại [g0_topk_evidence.md](g0_topk_evidence.md).

- 28/10/2026: chạy lại baseline 100 query và Top-K 10 query trong `outputs/g0_repro_check/`; G0 metric CSV, ranked predictions, inputs/revision và Top-K CSV (115 dòng) có SHA-256 trùng artifact cũ.
- Người dùng xác nhận đã tự vẽ và giải thích sơ đồ pipeline theo yêu cầu G0.4. G0 được chuyển từ “Đạt có điều kiện” thành “Đạt”; sơ đồ trong repository chỉ là tài liệu hỗ trợ, không được dùng làm bằng chứng thay cho xác nhận này.

## Tuần 2 — G1: chuẩn bị dữ liệu và evaluator

- Chuẩn hóa benchmark Zalo AI Legal Text Retrieval 2021, revision `5fb3df4300b3a81455fe09af444ec159afa8d212`.
- Manifest ghi **61.425 văn bản**, **3.196 query**; split gồm 2.300 train, 256 validation, 640 test.
- Tạo schema chuẩn và manifest/checksum; ghi nhận kiểm tra ID, qrels tham chiếu corpus và trùng lặp chính xác.
- Evaluator hỗ trợ Recall@10, Recall@50, MRR, MAP, nDCG@10. Toàn bộ 9 test hiện có đạt sau khi bổ sung test BM25 retrieval/save/load và kiểm tra evaluator từ chối ID ngoài corpus.
- Lệnh `.\.venv\Scripts\python.exe -m src.data.prepare_g1 --verify` thành công: 6 tệp xử lý và 7 tệp nguồn khớp manifest.

**Giới hạn:** G1 xác nhận dữ liệu/evaluator, không phải retrieval trên Zalo. Chưa có metric BM25 Zalo được xác nhận. Chi tiết manifest và kiểm tra nằm tại `data/processed/benchmarks/zalo_2021/manifest.json`, `configs/g1_data_lock.json`, `outputs/reports/g1_data_lock/`.

## Tuần 3 — G2: BM25 B0 trên Zalo

- Thêm `src/evaluation/run_bm25.py`; đặt tên theo chức năng, không theo tuần. Runner fit một lần trên 61.425 corpus docs rồi đánh giá baseline `k1=1.5,b=0.75` và lưới 9 cấu hình `k1={1.2,1.5,1.8}`, `b={0.5,0.75,1.0}` trên 256 query validation, depth 100.
- Tokenization giữ nguyên đúng mã tham khảo Daijestic revision `92fc24310adf26fd401573003028689e5cacc289`: `clean_text`, Underthesea `word_tokenize`, stopwords. Index dùng title + text. Test split không được đọc.
- Tuning chọn theo nDCG@10 validation, tie-break theo MAP, MRR, Recall@10, Recall@50, latency p95. Kết quả mặc định: R@10 .859375, R@50 .949219, MRR/MAP .618477, nDCG@10 .672548. Cấu hình chọn `k1=1.2,b=.75`: R@10 .855469, R@50 .949219, MRR/MAP .623093, nDCG@10 .675143. Gain nDCG nhỏ, Recall@10 giảm; không khẳng định cải thiện có ý nghĩa thống kê.
- Latency truy vấn nạp sẵn index: default p50/p95 158.565/317.389 ms; selected 165.624/304.356 ms. Thời gian fit progress bar khoảng 35:02; lượt đầu lỗi cuối khâu ghi metadata nên timer đo riêng không được lưu.
- Lượt đầu đã tạo index 91.617.306 byte, 9 prediction files và metric; lỗi dùng relative output path làm `Path.relative_to` dừng trước khi ghi `run_config.json`/log. Chuẩn hóa output path và thêm `--reuse-index`; chạy lại cả 9 cấu hình. SHA-256 predictions và metric values của cả 9 cấu hình trùng hoàn toàn. Evaluator CLI chạy độc lập cho default/selected, đủ 256 qid, không qid thiếu và metric khớp.
- Lệnh chính: `.\.venv\Scripts\python.exe -m src.evaluation.run_bm25 --top-k 100 --output-dir outputs\bm25_zalo_validation_20261028`; tái lập: thêm `--reuse-index outputs\bm25_zalo_validation_20261028\bm25_index.pkl`.
- Artifact: `outputs/bm25_zalo_validation_20261028/` gồm `bm25_index.pkl`, predictions, `metrics_comparison.csv`, `per_query/`, `standalone_evaluation/`, config, log và provenance. Lỗi/khôi phục chi tiết ở `index_build_provenance.json`.
- 9 test đạt; G2 **đạt theo tiêu chí đã giao** vì B0/replay trên validation tái tạo đúng predictions/metric. Test chưa đánh giá và không có claim về generalization.

## Khảo sát pipeline tham khảo — kiến trúc hybrid

- Đối chiếu README và mã nguồn repository `chisngooo/Vietnamese-Legal-Document-Retrieval` tại revision `366e8fb978d97b773d1cd16a92cc0de5445208dd`.
- Xác nhận trong mã: chunk 400 từ/overlap 50; BM25 dùng Underthesea tokenizer và `BM25Okapi`; Dense dùng BGE-M3, embedding chuẩn hóa, FAISS `IndexFlatIP` và mapping về `aid/chunk_id`; hai nhánh được hợp nhất bằng `product_rank` trong cấu hình script.
- Ghi nhận sai khác giữa tài liệu và code: README mô tả Top-10 sau reranking nhưng script reranker chỉ sắp xếp/ghi danh sách ứng viên; không cắt Top-K. README hướng dẫn batch 128, trong khi mặc định script là 16.384. Sơ đồ giữ đúng hành vi script và nêu rõ sai khác.
- Đầu ra sơ đồ: `docs/research_architecture.svg` (ảnh xem/chèn vào báo cáo).
- Đây là sơ đồ phân tích repository tham khảo theo yêu cầu; các thành phần đó không đồng nghĩa đã được tích hợp vào project DATN.

## Ghi chú về hồ sơ phiên

Nhật ký này tổng hợp artifact và các phiên trước chỉ truy cập được một phần. Không khẳng định lưu toàn bộ lịch sử hội thoại. Ngày môi trường, lệnh cài đặt và phiên bản chi tiết nằm trong `docs/reproducibility/pip-freeze.txt` và `docs/reproducibility/source_manifest.json` nếu cần tra cứu.

