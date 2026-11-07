# Vietnamese Legal Information Retrieval

**Đề tài:** Nghiên cứu và xây dựng hệ thống truy xuất văn bản pháp luật tiếng Việt sử dụng mô hình biểu diễn ngữ nghĩa và tái xếp hạng
**Tiến độ:** Đã hoàn thành G0–G3 (tuần 1–4); G3 được nghiệm thu trên validation của benchmark Zalo 2021.

## 1. Mục tiêu và phạm vi

Dự án xây dựng hệ thống nhận truy vấn pháp lý tiếng Việt và trả về danh sách văn bản liên quan được xếp hạng. Mục tiêu thực nghiệm hiện tại là thiết lập baseline từ khóa BM25 (B0), xây dựng dense retrieval BGE-M3 với FAISS (B1), rồi so sánh chất lượng truy xuất trên cùng benchmark và giao thức đánh giá.

Đến hết tuần 4, G0, G1, G2 và G3 đã hoàn tất theo phạm vi được mô tả bên dưới. B1 là dense retrieval trên toàn corpus, chưa phải hệ thống hybrid hay reranker. Hybrid fusion, reranking và đánh giá test chưa thực hiện; không suy rộng kết quả validation sang test.

## 2. Dữ liệu và giao thức đánh giá

### 2.1. Baseline ban đầu G0

- **BKAI Legal Retrieval:** subset có chọn lọc 5.000 văn bản.
- **YuITC Vietnamese Legal Documents:** chuẩn bị 500 query/qrel; kết quả G0 được tính trên 100 query.
- G0 dùng để kiểm tra pipeline và xem Top-K. Các metric này không đại diện cho toàn bộ BKAI/YuITC và không so sánh trực tiếp với kết quả Zalo.

### 2.2. Benchmark chính G1–G3

Dùng **Zalo AI Legal Text Retrieval 2021**, revision `5fb3df4300b3a81455fe09af444ec159afa8d212`:

- Corpus: 61.425 văn bản; 3.196 query.
- Train/validation: 2.300/256 query từ phần nhãn phát triển; seed split `zalo-g1-v1`.
- Test chính thức: 640 query; được giữ nguyên và chưa đánh giá.
- Metric chính: Recall@10, Recall@50, MRR, MAP và nDCG@10.
- B0 và B1 được chấm trên cùng 256 query validation bằng evaluator của dự án. Không dùng test qrels để chọn cấu hình.

Dữ liệu chuẩn, split, schema và checksum được ghi trong `data/processed/benchmarks/zalo_2021/manifest.json` và `configs/g1_data_lock.json`.

## 3. Phương pháp và tiến độ nghiên cứu

| Giai đoạn | Phương pháp / công việc | Kết quả và phạm vi |
|---|---|---|
| **Tuần 1 · G0** | Boolean, TF-IDF, BM25 trên subset BKAI/YuITC; kiểm tra truy vấn Top-K. | Pipeline baseline chạy được; metric trên 100 query. Mã retrieval được gọi từ repository tham khảo đã pin revision, không phải toàn bộ tự cài từ đầu. |
| **Tuần 2 · G1** | Chuẩn hóa benchmark Zalo; khóa schema, split, checksum và evaluator. | Verify thành công 6 artifact xử lý và 7 artifact nguồn; test split được giữ lại. |
| **Tuần 3 · G2 / B0** | BM25 trên toàn corpus Zalo; đánh giá mặc định và lưới 9 cấu hình trên validation. | Chọn `k1=1.2, b=0.75` theo nDCG@10 validation; predictions và metric replay từ index khớp. |
| **Tuần 4 · G3 / B1** | BGE-M3 encode toàn corpus; L2-normalize embedding; lập FAISS `IndexFlatIP`; truy xuất Top-100 và đánh giá validation. | 61.425/61.425 vector, 1.024 chiều; 256 query; artifact tải về và kiểm tra được trên Windows. G3 đạt trên validation. |

### Thiết lập B1

- Checkpoint: `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`.
- Môi trường encode: Kaggle GPU Tesla T4, CUDA 12.8; Python 3.13.15, PyTorch 2.11.0+cu128, Sentence Transformers 5.7.0, FAISS 1.15.1.
- Embedding: float32, chiều 1.024, L2-normalized; inner product trên vector chuẩn hóa tương ứng cosine similarity.
- Index: FAISS exact `IndexFlatIP`; 960 shard, 64 tài liệu/shard.
- Tổng thời gian run ghi trong báo cáo: 5.437,3 giây; encode corpus 5.294,886 giây; build/save FAISS 0,506 giây.
- Query latency B1: p50 53,496 ms, p95 60,511 ms, gồm encode query và FAISS search, không gồm encode corpus.
- FAISS index: 251.596.845 byte; mapping: 1.576.182 byte.

## 4. Kết quả thực nghiệm

### 4.1. G0 trên subset BKAI/YuITC

| Phương pháp | Số query | Recall@10 | MAP | nDCG@10 |
|---|---:|---:|---:|---:|
| Boolean | 100 | 0,2050 | 0,1912 | 0,1960 |
| TF-IDF | 100 | 0,8800 | 0,7394 | 0,7795 |
| BM25 | 100 | 0,9450 | 0,8485 | 0,8767 |

### 4.2. B0 và B1 trên cùng validation Zalo

| Phương pháp | Recall@10 | Recall@50 | MRR | MAP | nDCG@10 | Latency p50/p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| B0 BM25 (`k1=1.2, b=0.75`) | 0,855469 | 0,949219 | 0,623093 | 0,623093 | 0,675143 | 152,780 / 279,512 |
| B1 BGE-M3 + FAISS | **0,921875** | **0,968750** | **0,717058** | **0,717058** | **0,764762** | 53,496 / 60,511 |

B1 có metric quality cao hơn B0 trong lần đo trên 256 query validation này. Đây là kết quả thực nghiệm mô tả trên validation, chưa phải kết luận về test hoặc ý nghĩa thống kê. Latency B0 và B1 đo trên phần cứng/môi trường khác nhau; vì vậy không dùng chênh lệch trên để kết luận B1 nhanh hơn B0.

Evaluator chạy lại trên 25.600 dòng predictions B1 (100 kết quả cho mỗi 256 query) và validation qrels cho kết quả khớp `metrics.json`. Index nạp được trên Windows; 61.425 ID trong mapping duy nhất và theo đúng thứ tự corpus.

## 5. Cài đặt và chạy lại

Các lệnh dưới đây dành cho PowerShell tại thư mục gốc repository. B1 đầy đủ đã được encode trên Kaggle GPU; chạy lệnh build trên CPU sẽ tốn thời gian và dung lượng đáng kể.

### 5.1. Môi trường

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 5.2. Chạy G0

```powershell
python -m src.data.prepare --max-docs 5000 --max-queries 500
python -m src.evaluation.run_baselines --max-queries 100 --top-k 10
python -m src.app.query --query "Điều kiện đăng ký kết hôn được pháp luật quy định như thế nào?" --top-k 5
```

### 5.3. Chạy G2/B0 trên validation Zalo

Fit index và chạy baseline/grid validation:

```powershell
python -m src.evaluation.run_bm25 --top-k 100 --output-dir outputs/bm25_zalo_validation_20261028
```

Tái tạo predictions từ index đã lưu:

```powershell
python -m src.evaluation.run_bm25 --top-k 100 --reuse-index outputs/bm25_zalo_validation_20261028/bm25_index.pkl --output-dir outputs/bm25_zalo_validation_20261028
```

### 5.4. Chạy G3/B1

Encode corpus, xây index, truy xuất và đánh giá theo cấu hình:

```powershell
python -m experiments.B1_dense
```

Nạp index đã tạo để chạy retrieval/evaluation, không encode lại corpus:

```powershell
python -m experiments.B1_dense --reuse-index
```

Xác minh data lock và chạy test suite:

```powershell
python -m src.data.prepare_g1 --verify
python -m unittest discover -s tests -v
```

## 6. Artifact và khả năng tái lập

- Cấu hình B1: `configs/dense.yaml`.
- Mã runner: `experiments/B1_dense.py`; module retrieval: `src/retrieval/`.
- Artifact B1 đã giải nén: `outputs/b1_dense_validation/` — gồm `dense.faiss`, `dense.faiss.json`, predictions, metrics, so sánh B0/B1, run config và manifest.
- Báo cáo nghiệm thu: `docs/reports/g3_acceptance.md`.
- Tiến độ và nhật ký: `docs/PROGRESS.md`, `docs/WORK_LOG.md`.
- ZIP gốc Kaggle được giữ ngoài repository tại `D:\LegalIR-Workspace\B1_BGE_M3_FAISS_validation_artifacts.zip`; không cần ZIP để nạp các artifact đã giải nén.
