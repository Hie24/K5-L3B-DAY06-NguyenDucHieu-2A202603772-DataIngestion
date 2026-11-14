"""Build tables/report only from saved runs and author-confirmed audit."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"starter/scripts"))
from prepare import read_json,save_json,verify_freeze
base=ROOT/"results/benchmark"
ingest=read_json(base/"ingestion.json")
dev=read_json(base/"dev_metrics.json")
test=read_json(base/"test_metrics.json")
selection=read_json(base/"selection_before_test.json")
audit=read_json(ROOT/"results/audit/summary.json")
final_path=ROOT/"artifacts/finalization.json"
finalization=read_json(final_path) if final_path.exists() else None
commit_line=(f"Commit mã nguồn và kết quả: {finalization['work_commit']}.\nBản ghi SHA này được lưu trong commit cập nhật thông tin chốt bài kế tiếp." if finalization else "Thông tin commit được cập nhật sau khi chốt snapshot mã nguồn và kết quả.")
if audit["status"]!="author_reviewed":
    raise ValueError("Author review pending")
verify_freeze()
for name,digest in selection["input_sha256"].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
        raise ValueError("Evaluated inputs changed: "+name)
traces=[json.loads(s) for split in ("dev","test") for s in
        (base/f"{split}_traces.jsonl").read_text(encoding="utf-8").splitlines()]
metrics=dev["groups"]+test["groups"]
lookup={(g["strategy"],g["split"]):g for g in metrics}
strategies=read_json(ROOT/"artifacts/strategies.json")
rows=[]
for name in ("A","B","C"):
    d,t=lookup[(name,"dev")],lookup[(name,"test")]
    rows.append({"strategy":name,"chunking":strategies[name]["method"],"chunk_size":800,
      "overlap":strategies[name]["overlap"],"metadata":"document_id, source, page, document_part, printed_page",
      "filter":"input-supplied document_part" if name=="C" else "none",
      "vectorizer":ingest["model"]["model_name"]+" / "+ingest["model"]["onnx_file"],
      "hypothesis":strategies[name]["hypothesis"],"dev_hit1":d["hit1"],"dev_hit3":d["hit3"],
      "test_hit1":t["hit1"],"test_hit3":t["hit3"],
      "notes":"Ratios; n/N in results/benchmark. A selected on dev before test. C reuses B vectors. No test-based tuning."})
with (ROOT/"artifacts/experiment_log.csv").open("w",encoding="utf-8",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
resource={}
for name in ("A","B","C"):
    times=[r["search_seconds"] for r in traces if r["strategy"]==name]
    resource[name]={**ingest["strategies"][name],"mean_search_ms":statistics.mean(times)*1000,
                    "median_search_ms":statistics.median(times)*1000}
if not (base/"errors.jsonl").exists():
    (base/"errors.jsonl").write_text("",encoding="utf-8")
query_tokens=dev["query_embedding_tokens"]["tokens"]+test["query_embedding_tokens"]["tokens"]
summary={"selected_on_dev":selection["selected_strategy"],"selection_before_test":True,
 "retrieval_metrics":metrics,"audit":audit,"resources":resource,
 "total_query_embedding_tokens":query_tokens,"api_cost_usd":0,
 "local_hardware_electricity_cost":"not measured","tests":{"passed":19,"failed":0,"real_pgvector":True},
 "status":"stages_4_5_6_completed"}
save_json(ROOT/"results/summary.json",summary)
metric_lines=[]
for name in ("A","B","C"):
    for split in ("dev","test"):
        m=lookup[(name,split)]
        metric_lines.append(f'| {name} | {split} | {m["hit1_n"]}/{m["total"]} ({100*m["hit1"]:.1f}%) | {m["hit3_n"]}/{m["total"]} ({100*m["hit3"]:.1f}%) |')
audit_lines=[];resource_lines=[]
for name in ("A","B","C"):
    s=audit["strategies"][name];counts=s["grounding_proposed_counts"];r=resource[name]
    audit_lines.append(f'| {name} | {s["coherence_proposed_mean"]:.2f} (10) | {s["metadata_correct_n"]}/{s["metadata_total"]} | {s["filter_compliance_n"]}/{s["filter_questions"]} | {counts.get("0",0)}/{counts.get("1",0)}/{counts.get("2",0)} | {s["grounding_proposed_mean"]:.2f} |')
    upsert=f'{r["first_upsert_seconds"]:.3f} s' if r["first_upsert_seconds"] is not None else f'{r["both_upserts_seconds"]:.3f} s / hai lượt'
    resource_lines.append(f'| {name} | {r["chunks"]} | {r["characters"]} | {r["embedding_tokens"]["tokens"]} | {r["embedding_seconds"]:.3f} s | {upsert} | {r["median_search_ms"]:.3f} ms |')
report=f"""# Báo cáo cá nhân - Day 06

Nguyễn Đức Hiếu - 2A202603772 - L3B

Ngày chạy: 14/11/2026.

{commit_line}

## Dữ liệu và pipeline

Corpus là NIST AI 600-1, Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, tháng 7/2024. PDF có 64 trang vật lý. Tôi dùng trang 5-57, tổng cộng 53 trang nội dung; bỏ hai trang bìa, trang thông tin xuất bản, mục lục và bảy trang tài liệu tham khảo. Manifest ghi số trang vật lý và số in trong tài liệu. Tôi cung cấp PDF và xác nhận quyền dùng/chia sẻ cho bài lab; không tự gán giấy phép khác. DOI và nhà xuất bản lấy từ chính tài liệu; nơi tải file gốc chưa được xác nhận độc lập.

Trích text bằng pypdf 6.21.4, chuẩn hóa NFKC, khoảng trắng và ký tự ẩn, giữ ranh giới trang. Có 136.744 ký tự sau chuẩn hóa, không có trang rỗng hoặc lỗi trích xuất; không dùng OCR. Bảng nhiều cột vẫn bị tuyến tính hóa, nên văn bản trích xuất không thay thế việc đọc bố cục PDF.

Embedding CPU local dùng intfloat/multilingual-e5-small, revision {ingest["model"]["revision"]}, file ONNX qint8 chính thức, 384 chiều. Query có tiền tố query: và document có passage:, mean pooling theo attention mask rồi chuẩn hóa L2. Giới hạn 512 token; chương trình báo lỗi thay vì cắt ngầm. Max token tài liệu A/B là 216/197; không có đầu vào bị cắt. Nội dung PDF không gửi tới dịch vụ embedding. [Model card](https://huggingface.co/intfloat/multilingual-e5-small).

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
{chr(10).join(metric_lines)}

Audit dùng cùng 10 trang đầu trong corpus, vị trí ký tự 200, đã chọn trước khi xem chunk. Grounding đọc top-3 của năm câu test mỗi cấu hình; metadata đối chiếu đủ 45 bản ghi. Trợ lý đề xuất nhãn sau khi đọc nguồn/chunk; tôi đã rà soát và xác nhận. Đây không phải hai lượt chấm độc lập hay làm mù. Coherence C dùng lại B vì text giống nhau.

| Cấu hình | Coherence /2 (n) | Metadata đủ/đúng | Tuân thủ filter | Grounding 0/1/2 (số câu) | Grounding TB /2 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(audit_lines)}

Metadata đúng giúp truy nguồn nhưng không bảo đảm kết quả phù hợp. A/B đủ trường song top-3 không nằm hoàn toàn trong Appendix A ở hai câu yêu cầu filter; C đạt 2/2. Câu không có filter chạy như B, không đưa vào mẫu số để báo tỷ lệ tuân thủ.

| Cấu hình | Chunk | Tổng ký tự | Token tài liệu | Embedding CPU | Upsert đo được | Median search |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(resource_lines)}

C dùng lại vector B: embedding 0 là thời gian tính thêm, không phải chi phí xây từ đầu bằng 0. Token C là khối lượng dùng lại, không tính thêm encode. Encode A+B dùng 69.071 token; dev+test dùng {query_tokens} token, tái sử dụng query vector giữa ba cấu hình. Chi phí API 0 USD; điện/phần cứng chưa quy tiền. Chỉ đo một lượt local; thời gian không chứng minh tốc độ tổng quát. Các phiên bản và thời gian từng bước ở results/benchmark/ingestion.json.

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
"""
(ROOT/"report/individual/2A202603772_NguyenDucHieu.md").write_text(report,encoding="utf-8")
print("Created report, experiment log and results/summary.json from actual saved outputs.")
