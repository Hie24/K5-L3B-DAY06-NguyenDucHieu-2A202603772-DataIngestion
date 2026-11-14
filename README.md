# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

## Chạy bài làm LAB06 (PowerShell)

Bản chạy dùng Python 3.12.14, embedding local `intfloat/multilingual-e5-small` (ONNX qint8, 384 chiều) và PostgreSQL + pgvector Docker. Không cần API key. PDF nằm ở `starter/data/TailieuLAB06.pdf`; nguồn, quyền sử dụng và các trang được chọn nằm ở [data/manifest.json](data/manifest.json).

Từ thư mục gốc repo, cài môi trường và kiểm tra database:

```powershell
cd starter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -p day6_student_starter up -d --wait
.\.venv\Scripts\python.exe -B scripts/check_setup.py
.\.venv\Scripts\python.exe -B scripts/download_model.py
```

Nếu PowerShell chưa nhận lệnh `docker` trên máy hiện tại, thêm thư mục Docker vào PATH của phiên trước khi chạy Compose:

```powershell
$env:Path = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:Path"
```

Giữ thư mục làm việc ở `starter/`. Chạy theo thứ tự sau, dùng corpus/chunk và benchmark đã khóa trong repo:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -B -m src.run ingest --results-dir results/reproduction
.\.venv\Scripts\python.exe -B -m src.run dev --results-dir results/reproduction
.\.venv\Scripts\python.exe -B -m src.run test --results-dir results/reproduction
$env:LAB06_INTEGRATION = '1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Đường dẫn `--results-dir` tính từ gốc repo. Mỗi lượt chạy lại cần một thư mục kết quả mới; chương trình từ chối ghi đè trace. Pha `dev` chọn cấu hình trước khi pha `test` được phép chạy. Nạp lại database giữ nguyên ID và không nhân đôi chunk.

Kết quả gốc ở [results/summary.json](results/summary.json), trace ở `results/benchmark/`, nhãn đã được tác giả rà soát ở `results/audit/`. Xác nhận audit hiện tại chỉ áp dụng cho các đầu vào có hash trong `artifacts/author_review.json`. Xem [báo cáo cá nhân](report/individual/2A202603772_NguyenDucHieu.md) và [nhật ký thí nghiệm](artifacts/experiment_log.csv).
