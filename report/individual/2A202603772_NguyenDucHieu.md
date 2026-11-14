# Báo cáo cá nhân - Day 06

Nguyễn Đức Hiếu - 2A202603772 - L3B

Ngày chạy: 14/11/2026.

Thông tin commit được cập nhật sau khi chốt snapshot mã nguồn và kết quả.

## Dữ liệu và pipeline

Corpus là NIST AI 600-1, Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, tháng 7/2024. PDF có 64 trang vật lý. Tôi dùng trang 5-57, tổng cộng 53 trang nội dung; bỏ hai trang bìa, trang thông tin xuất bản, mục lục và bảy trang tài liệu tham khảo. Manifest ghi số trang vật lý và số in trong tài liệu. Tôi cung cấp PDF và xác nhận quyền dùng/chia sẻ cho bài lab; không tự gán giấy phép khác. DOI và nhà xuất bản lấy từ chính tài liệu; nơi tải file gốc chưa được xác nhận độc lập.

Trích text bằng pypdf 6.21.4, chuẩn hóa NFKC, khoảng trắng và ký tự ẩn, giữ ranh giới trang. Có 136.744 ký tự sau chuẩn hóa, không có trang rỗng hoặc lỗi trích xuất; không dùng OCR. Bảng nhiều cột vẫn bị tuyến tính hóa, nên văn bản trích xuất không thay thế việc đọc bố cục PDF.

Embedding CPU local dùng intfloat/multilingual-e5-small, revision 614241f622f53c4eeff9890bdc4f31cfecc418b3, file ONNX qint8 chính thức, 384 chiều. Query có tiền tố query: và document có passage:, mean pooling theo attention mask rồi chuẩn hóa L2. Giới hạn 512 token; chương trình báo lỗi thay vì cắt ngầm. Max token tài liệu A/B là 216/197; không có đầu vào bị cắt. Nội dung PDF không gửi tới dịch vụ embedding. [Model card](https://huggingface.co/intfloat/multilingual-e5-small).

Lưu bền vững bằng PostgreSQL 16.16 + pgvector 0.8.7, database day6_lab, bảng lab06_chunks, Docker volume day6_student_starter_pg_data. Tìm exact cosine, không HNSW/IVFFlat; SQL có tham số. Metadata gồm document_id, source, page, vị trí ký tự, printed_page và document_part. document_part có hai giá trị main_body/appendix_a, lấy từ ranh giới phần trong nguồn, dùng để lọc theo yêu cầu có sẵn của người dùng. [pgvector](https://github.com/pgvector/pgvector).

## Cấu hình và benchmark

- A: fixed-size 800 ký tự, overlap 100, không filter.
- B: theo đoạn/heading/action row, tối đa 800 ký tự, không overlap/filter.
- C: dùng đúng chunk, metadata và vector B; chỉ thêm filter khi câu hỏi/ngữ cảnh cung cấp trước.

A-B thay toàn bộ chính sách chunking, kể cả overlap; B-C chỉ thay filter. Hai lần nạp cho A/B/C đều giữ số hàng 213/381/381; mở kết nối mới vẫn đúng số đó. Có 381 hàng B/C giống text, metadata và vector. Kiểm thử transaction thay nguồn đã xác nhận loại chunk cũ, rồi rollback bản ghi kiểm thử.

Benchmark có 20 câu tiếng Việt, evidence tiếng Anh: 15 dev ở phần chính và 5 test ở Appendix A; bốn câu filter, hai câu thuộc test. Evidence được kiểm tra trước khi khóa. Hash corpus/câu hỏi/protocol không đổi. Vì chỉ có một tài liệu và các phần lặp khái niệm, đây không phải chia tập độc lập theo tài liệu.

Tiêu chí chốt trước test: ưu tiên dev Evidence Hit@3, rồi Hit@1, số chunk ít hơn, cuối cùng thứ tự ID. **A được chọn trên dev trước khi chạy test.** Không chọn lại theo kết quả C trên test.

## Kết quả

Một hit cần một chunk đúng nguồn/trang và đủ evidence. Cột dưới dùng toàn bộ trích dẫn đã chuẩn hóa khoảng trắng, gồm các nguồn thay thế đã ghi. Các miss được đọc lại trong results/audit/evidence_miss_review.json; chưa có bằng chứng thay thế nào được chấp nhận. Không gộp nhiều mảnh thiếu để tính hit bắt buộc.

| Cấu hình | Tập | Hit@1 (n/N) | Evidence Hit@3 (n/N) |
|---|---|---:|---:|
| A | dev | 9/15 (60.0%) | 12/15 (80.0%) |
| A | test | 2/5 (40.0%) | 3/5 (60.0%) |
| B | dev | 9/15 (60.0%) | 11/15 (73.3%) |
| B | test | 4/5 (80.0%) | 4/5 (80.0%) |
| C | dev | 9/15 (60.0%) | 11/15 (73.3%) |
| C | test | 4/5 (80.0%) | 5/5 (100.0%) |

Audit dùng cùng 10 trang đầu trong corpus, vị trí ký tự 200, đã chọn trước khi xem chunk. Grounding đọc top-3 của năm câu test mỗi cấu hình; metadata đối chiếu đủ 45 bản ghi. Trợ lý đề xuất nhãn sau khi đọc nguồn/chunk; tôi đã rà soát và xác nhận. Đây không phải hai lượt chấm độc lập hay làm mù. Coherence C dùng lại B vì text giống nhau.

| Cấu hình | Coherence /2 (n) | Metadata đủ/đúng | Tuân thủ filter | Grounding 0/1/2 (số câu) | Grounding TB /2 |
|---|---:|---:|---:|---:|---:|
| A | 1.00 (10) | 15/15 | 0/2 | 2/0/3 | 1.20 |
| B | 1.50 (10) | 15/15 | 0/2 | 1/0/4 | 1.60 |
| C | 1.50 (10) | 15/15 | 2/2 | 0/0/5 | 2.00 |

Metadata đúng giúp truy nguồn nhưng không bảo đảm kết quả phù hợp. A/B đủ trường song top-3 không nằm hoàn toàn trong Appendix A ở hai câu yêu cầu filter; C đạt 2/2. Câu không có filter chạy như B, không đưa vào mẫu số để báo tỷ lệ tuân thủ.

| Cấu hình | Chunk | Tổng ký tự | Token tài liệu | Embedding CPU | Upsert đo được | Median search |
|---|---:|---:|---:|---:|---:|---:|
| A | 213 | 152704 | 36131 | 6.495 s | 0.114 s | 3.169 ms |
| B | 381 | 136394 | 32940 | 8.164 s | 0.173 s | 3.348 ms |
| C | 381 | 136394 | 32940 | 0.000 s | 0.313 s / hai lượt | 2.358 ms |

C dùng lại vector B: embedding 0 là thời gian tính thêm, không phải chi phí xây từ đầu bằng 0. Token C là khối lượng dùng lại, không tính thêm encode. Encode A+B dùng 69.071 token; dev+test dùng 564 token, tái sử dụng query vector giữa ba cấu hình. Chi phí API 0 USD; điện/phần cứng chưa quy tiền. Chỉ đo một lượt local; thời gian không chứng minh tốc độ tổng quát. Các phiên bản và thời gian từng bước ở results/benchmark/ingestion.json.

## Phân tích và kết luận

**A-B:** A đạt 12/15 dev Hit@3, hơn B một câu dù coherence thấp hơn. Cửa sổ có overlap giữ ngữ cảnh dài nhưng hay cắt giữa câu. B giữ nhiều đoạn trọn ý hơn, song tạo 381 vector và có thể trả footnote hoặc đoạn quá ngắn. Không thể kết luận chia theo cấu trúc luôn tốt hơn.

**B-C:** dev không tăng. Trên test, filter đưa đoạn đúng trang 53 vào rank 3 của T01, tăng Hit@3 từ 4/5 lên 5/5. T03 vẫn hit rank 1 nhưng cả top-3 của C đều thuộc Appendix A. Đây là tác dụng đo được của document_part, không chỉ là có đủ metadata.

Hai ví dụ lỗi:

1. **T01 ở A:** top-3 trang 16, 12, 40 không có câu về laboratory và real-world settings ở trang 53. Một kết quả chỉ là mảnh cuối đoạn có từ Appendix A. A/B thiếu evidence; filter C mới đưa đúng đoạn vào top-3.
2. **D11:** cần GV-1.2-001 ở trang 18. A trả đúng trang nhưng chunk GV-1.3-002; B/C trả hành động khác. Đúng trang hoặc gần nghĩa chung chưa đủ để tính hit.

Mẫu coherence B trang 9 còn bắt đầu bằng phần câu từ trang trước, thiếu tên rủi ro. Giữ trang giúp truy vết nhưng không tự giữ đủ ngữ cảnh.

Tôi giữ **A là lựa chọn theo dev**. C tốt hơn trên năm câu test, nhưng một câu đã tương ứng 20 điểm phần trăm. Nếu tiếp tục cải tiến, cần tập đánh giá mới cho ngữ cảnh qua trang, bảng/footnote và mã hành động. Chưa sửa các yếu tố đó trên test hiện tại.

Hạn chế: một PDF, câu hỏi và nguồn khác ngôn ngữ, model qint8 cố định, audit có nguy cơ thiên lệch do đề xuất-rà soát, chỉ một lượt đo thời gian. Hit@3 không phải độ chính xác trả lời LLM; pipeline này không sinh câu trả lời LLM.

### Kiểm chứng và chạy lại

- data/manifest.json: nguồn/quyền, quy tắc đếm và từng trang.
- benchmark/: câu hỏi, protocol, hash khóa trước retrieval.
- results/benchmark/: ingest, lựa chọn trước test, toàn bộ top-3 và metric.
- results/audit/: mẫu, nhãn, lý do, metadata/filter; artifacts/author_review.json lưu xác nhận tác giả.
- artifacts/experiment_log.csv: giả thuyết và tỷ lệ A/B/C.
- README có lệnh setup/run; 19/19 kiểm thử qua, gồm pgvector thật.
- Codex hỗ trợ code, đối chiếu nguồn và đề xuất audit. Kết quả được kiểm bằng chạy local, test, trace và tác giả rà soát; không dùng LLM judge.
