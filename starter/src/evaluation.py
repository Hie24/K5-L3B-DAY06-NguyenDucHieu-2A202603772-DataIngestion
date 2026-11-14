"""Evidence metrics with explicit source/page checks; never infer human audit labels."""
import re
import unicodedata
from collections import defaultdict
from typing import Any


def canonical(text):
    return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",text)).strip()


def evaluate_query(question: dict[str,Any],hits: list[dict[str,Any]]) -> dict[str,Any]:
    gold=question.get("gold_evidence") or [{
        "source_id":question["gold_source_id"],"page":question["gold_page"],
        "evidence_quote":question["evidence_quote"]}]
    reviewed=[]
    for rank,hit in enumerate(hits[:3],1):
        source_match=any(hit["document_id"]==g["source_id"] and hit["page"]==g["page"] for g in gold)
        evidence_match=any(hit["document_id"]==g["source_id"] and hit["page"]==g["page"]
                           and canonical(g["evidence_quote"]) in canonical(hit["text"]) for g in gold)
        reviewed.append({**hit,"rank":rank,"gold_source_page_match":source_match,
                         "enough_literal_gold_evidence":evidence_match})
    return {"question_id":question["id"],"split":question["split"],
            "question":question["question"],"expected_answer":question["expected_answer"],
            "gold_evidence":gold,"requested_filter":question.get("filter",{}),
            "hits":reviewed,"hit1":bool(reviewed and reviewed[0]["enough_literal_gold_evidence"]),
            "hit3":any(h["enough_literal_gold_evidence"] for h in reviewed),
            "metric_method":"single chunk, correct source/page, full whitespace-normalized evidence quote; equivalent evidence needs explicit separate review"}

def summarize(traces: list[dict[str,Any]]) -> dict[str,Any]:
    groups=defaultdict(list)
    for trace in traces:
        groups[(trace["strategy"],trace["split"])].append(trace)
    return {"groups":[{"strategy":strategy,"split":split,"total":len(rows),
                      "hit1_n":sum(r["hit1"] for r in rows),"hit3_n":sum(r["hit3"] for r in rows),
                      "hit1":sum(r["hit1"] for r in rows)/len(rows),
                      "hit3":sum(r["hit3"] for r in rows)/len(rows)}
                     for (strategy,split),rows in sorted(groups.items())]}
