"""Preparation checkpoints only: corpus -> freeze benchmark -> chunks; no retrieval."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "starter"))
from src.ingestion import load_pdf

OUT = ROOT / "results" / "preparation"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(text):
    return re.sub(r"\s+", " ", text).strip()


def read_pages():
    return [json.loads(line) for line in (OUT / "normalized_pages.jsonl").read_text(encoding="utf-8").splitlines()]


def corpus():
    from dataclasses import asdict
    config = read_json(ROOT / "data/corpus_config.json")
    pdf = ROOT / config["source_path"]
    errors = []
    pages = load_pdf(pdf, config["source_id"], config["source_url"], error_log=errors)
    include = set(config["included_physical_pages"])
    groups = {p: group["document_part"] for group in config["metadata_groups"] for p in group["pages"]}
    excluded = {p: group["reason"] for group in config["excluded_pages"] for p in group["pages"]}
    if set(range(1, len(pages)+1)) != include | set(excluded) or include & set(excluded):
        raise ValueError("Every physical page must have exactly one inclusion decision")
    normalized, audit = [], []
    for page in pages:
        printed = None
        text = page.text
        lines = text.splitlines()
        # This corpus prints its page label as the first extracted line.
        if lines and lines[0].isdigit():
            printed = int(lines.pop(0))
            text = "\n".join(lines).strip()
        row = {"page": page.page, "page_id": page.metadata["page_id"],
               "raw_chars": page.metadata["raw_chars"], "normalized_chars": len(text),
               "printed_page": printed, "included": page.page in include,
               "extraction_status": page.metadata["extraction_status"],
               "reason": "Nội dung chính/phụ lục có nội dung" if page.page in include else excluded[page.page]}
        audit.append(row)
        if page.page in include:
            if not text or page.metadata["extraction_status"] != "ok":
                raise ValueError(f"Included page {page.page} has no usable text")
            if page.page not in groups:
                raise ValueError(f"Missing source-based metadata for page {page.page}")
            page.text = text
            page.metadata.update({"document_part": groups[page.page], "printed_page": printed,
                                  "language": "en", "document_type": "technical_report"})
            normalized.append(asdict(page))
    if len(normalized) < config["minimum_content_pages"]:
        raise ValueError("Not enough useful content pages")
    manifest = {
        **config, "accessed_at": "2026-11-14", "access_method": "Local PDF inspection; no claim of an online download on this date",
        "file_sha256": sha(pdf), "physical_page_count": len(pages),
        "content_page_count": len(normalized), "page_number_convention": "1-based physical PDF page; printed_page recorded separately",
        "normalization": "NFKC, whitespace, soft hyphen/zero-width cleanup; preserve line boundaries. Remove only observed leading numeric printed-page labels; do not merge pages or silently OCR.",
        "pages": audit, "normalized_characters": sum(len(p["text"]) for p in normalized),
        "error_count": len(errors),
    }
    save_json(ROOT / "data/manifest.json", manifest)
    save_jsonl(OUT / "normalized_pages.jsonl", normalized)
    save_jsonl(OUT / "extraction_events.jsonl", errors)
    save_json(OUT / "page_audit.json", audit)
    save_json(OUT / "environment.json", {
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in ("pypdf", "psycopg", "psycopg-binary", "python-dotenv")},
        "stage": "1-3 only", "embedding_model_loaded": False, "retrieval_run": False,
    })
    print(json.dumps({"physical_pages":len(pages),"content_pages":len(normalized),
                      "excluded_pages":len(excluded),"characters":manifest["normalized_characters"],
                      "extraction_events":len(errors)}, ensure_ascii=False))


def validate_benchmark():
    questions = read_json(ROOT / "benchmark/questions.json")
    pages = read_pages()
    lookup = {(p["document_id"], p["page"]):p for p in pages}
    ids = [q["id"] for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate question ID")
    splits = Counter(q["split"] for q in questions)
    if len(questions) < 20 or splits["dev"] < 15 or splits["test"] < 5:
        raise ValueError("Benchmark split is too small")
    if sum(bool(q.get("filter")) for q in questions) < 3 or not any(q.get("filter") for q in questions if q["split"]=="test"):
        raise ValueError("Not enough metadata-filter questions")
    checks = []
    for q in questions:
        page = lookup[(q["gold_source_id"],q["gold_page"])]
        quote = canonical(q["evidence_quote"])
        if not quote or quote not in canonical(page["text"]):
            raise ValueError(f"Evidence not found: {q['id']}")
        if not q.get("expected_answer"):
            raise ValueError(f"Missing answer: {q['id']}")
        if any(page["metadata"].get(k) != v for k,v in q.get("filter",{}).items()):
            raise ValueError(f"Gold page violates filter: {q['id']}")
        if q.get("filter") and not q.get("filter_context"):
            raise ValueError(f"Filter must be pre-supplied by context: {q['id']}")
        if q.get("filter") and (set(q["filter"]) - {"document_part"}):
            raise ValueError("This benchmark permits only its declared metadata field")
        # Every verbatim alternative occurrence is recorded, rather than penalized.
        alternatives = [{"source_id":p["document_id"],"page":p["page"],"evidence_quote":q["evidence_quote"]}
                        for p in pages if quote in canonical(p["text"])
                        and all(p["metadata"].get(k)==v for k,v in q.get("filter",{}).items())]
        if q.get("gold_evidence") != alternatives:
            raise ValueError(f"Missing/inaccurate alternative gold evidence: {q['id']}")
        checks.append({"id":q["id"],"split":q["split"],"primary_page":q["gold_page"],
                       "quote_found":True,"filter_valid":True,"gold_occurrences":len(alternatives),
                       "method":"literal quote after whitespace normalization; assistant checked question/answer context; not a user audit label"})
    return questions, checks


def freeze_benchmark():
    questions, checks = validate_benchmark()
    protocol = ROOT / "benchmark/protocol.json"
    if not protocol.exists():
        raise ValueError("Define split and selection protocol before freezing")
    files = ["benchmark/questions.json","benchmark/protocol.json","data/corpus_config.json","results/preparation/normalized_pages.jsonl"]
    hashes = {name:sha(ROOT/name) for name in files}
    freeze_path = ROOT / "benchmark/freeze.json"
    if freeze_path.exists():
        previous = read_json(freeze_path)
        if previous["sha256"] != hashes:
            raise ValueError("Benchmark/source changed after freeze; do not silently replace the holdout")
        print("Existing benchmark freeze verified; unchanged.")
    else:
        save_json(freeze_path, {"frozen_at":datetime.now(timezone.utc).isoformat(),
                               "sha256":hashes, "retrieval_run_at_freeze":False,
                               "note":"Freeze after gold/source verification and before generating chunk outputs; no embedding or retrieval run."})
        print("Benchmark frozen before chunk generation and retrieval.")
    save_json(OUT/"benchmark_validation.json", {
        "questions":len(questions),"dev":sum(q["split"]=="dev" for q in questions),
        "test":sum(q["split"]=="test" for q in questions),
        "filter_questions":sum(bool(q.get("filter")) for q in questions), "checks":checks})
    # Fixed positions, selected without inspecting chunk results or retrieval scores.
    save_json(ROOT/"benchmark/coherence_positions.json", {
        "selection_rule":"First 10 included physical pages in ascending order, character offset 200 in normalized page text.",
        "human_scores_entered":False,
        "positions":[{"document_id":p["document_id"],"page":p["page"],"char_offset":min(200,len(p["text"])-1)}
                     for p in read_pages()[:10]]})


def verify_freeze():
    m=read_json(ROOT/"benchmark/freeze.json")
    for name,digest in m["sha256"].items():
        if sha(ROOT/name)!=digest:
            raise ValueError(f"Frozen input changed: {name}")


def chunks():
    verify_freeze()
    from src.chunking import fixed_size, by_paragraph
    from src.models import DocumentPage
    from dataclasses import asdict
    import statistics
    import time
    cfg=read_json(ROOT/"artifacts/strategies.json")
    pages=[DocumentPage(**p) for p in read_pages()]
    summary={}
    for name,func in (("A",fixed_size),("B",by_paragraph)):
        started=time.perf_counter()
        params=cfg[name]
        output=[]
        for page in pages:
            parts=func(page,params["chunk_size"],params["overlap"]) if name=="A" else func(page,params["chunk_size"])
            for c in parts:
                assert c.text==page.text[c.metadata["char_start"]:c.metadata["char_end"]]
                assert c.metadata["document_part"]==page.metadata["document_part"]
                assert len(c.text)<=params["chunk_size"]
            covered=set()
            for c in parts:
                covered.update(range(c.metadata["char_start"],c.metadata["char_end"]))
            if any(i not in covered for i,ch in enumerate(page.text) if not ch.isspace()):
                raise ValueError(f"Chunking lost source text: {name} page {page.page}")
            output.extend(parts)
        rows=[asdict(c) for c in output]
        lengths=[len(c.text) for c in output]
        if len({c.chunk_id for c in output})!=len(output):
            raise ValueError("Duplicate chunk ID")
        save_jsonl(OUT/f"chunks_{name}.jsonl",rows)
        summary[name]={"chunk_count":len(rows),"characters":sum(lengths),"min_chars":min(lengths),
                       "max_chars":max(lengths),"mean_chars":round(statistics.mean(lengths),2),
                       "median_chars":statistics.median(lengths),"chunking_seconds":round(time.perf_counter()-started,6),
                       "token_count":None,"embedding_cost":None,"ingest_seconds":None,
                       "note":"Only chunk creation measured. Model tokens, embedding and database ingest not run."}
    summary["C"]={"reuses":"chunks_B.jsonl","chunk_count":summary["B"]["chunk_count"],
                  "filter_policy":"Same B chunks; apply document_part only when query context supplies it.",
                  "retrieval_run":False}
    save_json(OUT/"chunk_statistics.json",summary)
    print(json.dumps(summary,ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["corpus","freeze-benchmark","chunks","verify"])
    args=parser.parse_args()
    {"corpus":corpus,"freeze-benchmark":freeze_benchmark,"chunks":chunks,"verify":verify_freeze}[args.phase]()


if __name__=="__main__":
    main()
