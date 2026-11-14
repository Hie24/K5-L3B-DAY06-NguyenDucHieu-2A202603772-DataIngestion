"""Assemble source-verifiable audit packets from explicitly reviewed proposals."""
import json
import hashlib
from pathlib import Path
import sys
from collections import Counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"starter/scripts"))
from prepare import save_json,read_json

out=ROOT/"results/audit"
out.mkdir(parents=True,exist_ok=True)
assess=read_json(ROOT/"artifacts/audit_assessments.json")
positions=read_json(ROOT/"benchmark/coherence_positions.json")["positions"]
pages={(p["document_id"],p["page"]):p for p in
       [json.loads(s) for s in (ROOT/"results/preparation/normalized_pages.jsonl").read_text(encoding="utf-8").splitlines()]}
coherence=[]
for strategy in ("A","B","C"):
    base="B" if strategy=="C" else strategy
    chunks=[json.loads(s) for s in (ROOT/f"results/preparation/chunks_{base}.jsonl").read_text(encoding="utf-8").splitlines()]
    for pos in positions:
        found=[c for c in chunks if c["page"]==pos["page"]
               and c["metadata"]["char_start"]<=pos["char_offset"]<c["metadata"]["char_end"]]
        if not found:
            raise ValueError("Preselected source position has no covering chunk")
        score,reason=assess["coherence"][base][str(pos["page"])]
        for chunk in found:
            coherence.append({"strategy":strategy,**pos,"chunk_id":chunk["chunk_id"],
                  "text":chunk["text"],"metadata":chunk["metadata"],"proposed_score":score,
                  "reason":reason,"same_text_as_B":strategy=="C","author_score":None})

traces=[json.loads(s) for s in (ROOT/"results/benchmark/test_traces.jsonl").read_text(encoding="utf-8").splitlines()]
grounding,metadata,filters=[],[],[]
for t in traces:
    score,reason=assess["grounding"][t["strategy"]][t["question_id"]]
    grounding.append({"strategy":t["strategy"],"question_id":t["question_id"],
                      "question":t["question"],"expected_answer":t["expected_answer"],
                      "gold_evidence":t["gold_evidence"],"hits":t["hits"],
                      "proposed_score":score,"reason":reason,"author_score":None})
    for h in t["hits"]:
        source=pages[(h["document_id"],h["page"])]
        m=h["metadata"]
        checks={
            "source":h["source"]==source["source"] and m["source"]==source["source"],
            "page":m["page"]==source["page"],
            "document_id":m["document_id"]==source["document_id"],
            "document_part":m["document_part"]==source["metadata"]["document_part"],
            "printed_page":m["printed_page"]==source["metadata"]["printed_page"],
            "span_text":h["text"]==source["text"][m["char_start"]:m["char_end"]],
        }
        metadata.append({"strategy":t["strategy"],"question_id":t["question_id"],"rank":h["rank"],
            "chunk_id":h["chunk_id"],"source":h["source"],"physical_page":h["page"],
            "metadata":m,"checks":checks,"mechanically_complete_and_correct":all(checks.values()),
            "source_review":"Assistant compared fields to normalized source and PDF page convention; human confirmation pending."})
    requested=t["requested_filter"]
    if requested:
        filters.append({"strategy":t["strategy"],"question_id":t["question_id"],
            "requested_filter":requested,"applied_filter":t["applied_filter"],
            "returned":len(t["hits"]),"all_top3_comply":len(t["hits"])==3 and all(
                all(h["metadata"].get(k)==v for k,v in requested.items()) for h in t["hits"])})

review_path=ROOT/"artifacts/author_review.json"
author_confirmed=False
if review_path.exists():
    approval=read_json(review_path)
    if approval["decision"]!="approved_proposed_labels":
        raise ValueError("Author review is not an approval")
    for name,digest in approval["input_sha256"].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError("Audit inputs changed after author confirmation: "+name)
    author_confirmed=True
    for row in coherence+grounding:
        row["author_score"]=row["proposed_score"]
        row["review_status"]="author_reviewed_and_approved"
    for row in metadata:
        row["source_review"]="Assistant source comparison reviewed and approved by author; see artifacts/author_review.json."

summary={}
for name in ("A","B","C"):
    c=[r for r in coherence if r["strategy"]==name]
    g=[r for r in grounding if r["strategy"]==name]
    m=[r for r in metadata if r["strategy"]==name]
    f=[r for r in filters if r["strategy"]==name]
    summary[name]={"coherence_n":len(c),"coherence_proposed_mean":sum(r["proposed_score"] for r in c)/len(c),
                  "grounding_n":len(g),"grounding_proposed_counts":dict(Counter(str(r["proposed_score"]) for r in g)),
                  "grounding_proposed_mean":sum(r["proposed_score"] for r in g)/len(g),
                  "metadata_correct_n":sum(r["mechanically_complete_and_correct"] for r in m),"metadata_total":len(m),
                  "filter_compliance_n":sum(r["all_top3_comply"] for r in f),"filter_questions":len(f),
                  "author_confirmed":author_confirmed}
save_json(out/"coherence_proposals.json",coherence)
save_json(out/"grounding_proposals.json",grounding)
save_json(out/"metadata_checks.json",metadata)
save_json(out/"filter_checks.json",filters)
save_json(out/"summary.json",{"status":"author_reviewed" if author_confirmed else "pending_author_review","assessor":assess["assessor"],
          "human_labels_entered":author_confirmed,"author_review":"artifacts/author_review.json" if author_confirmed else None,"strategies":summary})
save_json(out/"evidence_miss_review.json",{"reviewer":assess["assessor"],
          "accepted_equivalences":[],"notes":assess["semantic_miss_review"],
          "raw_metrics_unchanged":True})

lines=["# Phiếu rà soát audit","",
       "Nhãn do trợ lý đề xuất, tác giả đã rà soát và xác nhận qua hội thoại; xem artifacts/author_review.json." if author_confirmed else "Nhãn đề xuất chưa có xác nhận của tác giả.",
       "Các mẫu đầy đủ nằm trong JSON đi kèm. Không sửa kết quả truy xuất khi điều chỉnh nhãn; xác nhận hiện tại chỉ áp dụng cho hash đã lưu.",
       "","## Coherence: 10 vị trí nguồn đã chọn trước","",
       "| Cấu hình | Trang vật lý | Điểm đề xuất /2 | Lý do |","|---|---:|---:|---|"]
for row in coherence:
    lines.append(f'| {row["strategy"]} | {row["page"]} | {row["proposed_score"]} | {row["reason"]} |')
lines += ["","## Grounding: 5 câu test cho mỗi cấu hình","",
          "| Cấu hình | Câu | Điểm đề xuất /2 | Lý do |","|---|---|---:|---|"]
for row in grounding:
    lines.append(f'| {row["strategy"]} | {row["question_id"]} | {row["proposed_score"]} | {row["reason"]} |')
lines += ["","## Metadata và filter","",
          "| Cấu hình | Metadata đủ/đúng (kiểm tra máy) | Top-3 tuân thủ yêu cầu filter |","|---|---:|---:|"]
for name,s in summary.items():
    lines.append(f'| {name} | {s["metadata_correct_n"]}/{s["metadata_total"]} | {s["filter_compliance_n"]}/{s["filter_questions"]} |')
lines += ["","Đối chiếu đầy đủ: coherence_proposals.json, grounding_proposals.json, metadata_checks.json, filter_checks.json.",
          "Điểm 0/1/2 không được suy ra tự động từ Hit@3. Các mẫu C coherence có cùng text với B, không phải lần chấm độc lập.",
          "Trạng thái xác nhận: "+("author_reviewed" if author_confirmed else "pending_author_review")]
(out/"REVIEW.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
