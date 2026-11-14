"""Reproducible phases: ingest -> dev/select -> fixed test. No LLM generation."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
from dotenv import load_dotenv
from .models import Chunk
from .embeddings import MyEmbedder
from .store import PgVectorStore
from .evaluation import evaluate_query,summarize

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"starter/scripts"))
from prepare import verify_freeze


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows),encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def locked_inputs():
    freeze=read(ROOT/"benchmark/freeze.json")
    extra=["artifacts/strategies.json","artifacts/run_config.json","artifacts/model_files.json",
           "results/preparation/chunks_A.jsonl","results/preparation/chunks_B.jsonl",
           "starter/src/run.py","starter/src/embeddings.py","starter/src/store.py",
           "starter/src/evaluation.py","starter/src/models.py"]
    return {**freeze["sha256"],**{name:sha(ROOT/name) for name in extra}}


def model(config):
    started=time.perf_counter()
    value=MyEmbedder(config["model_name"],ROOT/config["model_dir"],revision=config["revision"],
                    onnx_file=config["onnx_file"],max_tokens=config["max_tokens"],
                    batch_size=config["batch_size"],threads=config["threads"])
    expected=read(ROOT/"artifacts/model_files.json")
    if any(value.file_hashes[name]!=expected["files"][name]["sha256"] for name in value.file_hashes):
        raise ValueError("Downloaded model bytes differ from locked manifest")
    return value,time.perf_counter()-started


def store(config):
    url=os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL missing; use starter/.env")
    value=PgVectorStore(url,config["dimensions"])
    value.create_schema()
    return value


def get_chunks(name):
    return [Chunk(**json.loads(line)) for line in
            (ROOT/f"results/preparation/chunks_{name}.jsonl").read_text(encoding="utf-8").splitlines()]


def ingest(out,config):
    if (out/"ingestion.json").exists():
        raise ValueError("Ingestion report exists; use a new --results-dir for another experiment")
    encoder,load_seconds=model(config)
    db=store(config)
    stats={}
    cache=ROOT/"results/cache"
    cache.mkdir(parents=True,exist_ok=True)
    started_all=time.perf_counter()
    try:
        sets={name:get_chunks(name) for name in ("A","B")}
        arrays={}
        for name,chunks in sets.items():
            print("Encoding documents",name,len(chunks),flush=True)
            started=time.perf_counter()
            arrays[name]=encoder.embed_documents([c.text for c in chunks])
            embed_seconds=time.perf_counter()-started
            token_stats=dict(encoder.last_stats)
            np.savez_compressed(cache/f"vectors_{name}.npz",vectors=np.asarray(arrays[name],dtype=np.float32))
            started=time.perf_counter()
            db.upsert(name,chunks,arrays[name])
            insert_seconds=time.perf_counter()-started
            initial_count=db.count(name)
            started=time.perf_counter()
            db.upsert(name,chunks,arrays[name])
            repeat_seconds=time.perf_counter()-started
            if initial_count!=len(chunks) or db.count(name)!=initial_count:
                raise ValueError("Re-ingest duplicated or lost rows")
            stats[name]={"chunks":len(chunks),"characters":sum(len(c.text) for c in chunks),
                         "embedding_seconds":embed_seconds,"embedding_tokens":token_stats,
                         "first_upsert_seconds":insert_seconds,"repeat_upsert_seconds":repeat_seconds,
                         "first_count":initial_count,"second_count":db.count(name),"api_cost_usd":0}
        started=time.perf_counter()
        db.upsert("C",sets["B"],arrays["B"])
        first=db.count("C")
        db.upsert("C",sets["B"],arrays["B"])
        if db.count("C")!=first or first!=len(sets["B"]):
            raise ValueError("C re-ingest mismatch")
        stats["C"]={**stats["B"],"embedding_seconds":0,"embedding_reused_from":"B",
                    "first_upsert_seconds":None,"repeat_upsert_seconds":None,
                    "both_upserts_seconds":time.perf_counter()-started,
                    "first_count":first,"second_count":db.count("C")}
        equal=db.conn.execute("""SELECT count(*) AS n FROM lab06_chunks b JOIN lab06_chunks c
            ON b.chunk_id=c.chunk_id AND c.strategy='C'
            WHERE b.strategy='B' AND b.text=c.text AND b.metadata=c.metadata AND b.embedding=c.embedding""").fetchone()["n"]
        if equal!=len(sets["B"]):
            raise ValueError("B and C are not exactly identical before filtering")
        db_info=db.conn.execute("""SELECT current_setting('server_version') AS postgresql,
            (SELECT extversion FROM pg_extension WHERE extname='vector') AS pgvector,
            pg_total_relation_size('lab06_chunks') AS table_bytes""").fetchone()
    finally:
        db.close()
    # A new connection confirms that rows persist beyond the ingest session.
    reopened=store(config)
    try:
        persistent={name:reopened.count(name) for name in ("A","B","C")}
    finally:
        reopened.close()
    save(out/"ingestion.json",{"completed_at":now(),"model":config,"model_load_seconds":load_seconds,
        "total_ingestion_wall_seconds":time.perf_counter()-started_all,"strategies":stats,
        "persistence_after_reconnect":persistent,"B_C_identical_rows":equal,"database":db_info,
        "input_sha256":locked_inputs(),"search_mode":"exact; no approximate vector index",
        "cost_note":"No paid API. Local hardware/electricity not priced.",
        "software":{"python":platform.python_version(),**{p:importlib.metadata.version(p) for p in
                    ("numpy","onnxruntime","tokenizers","huggingface-hub","psycopg","pypdf")}}})
    print("Ingestion and repeat/reconnect checks passed:",persistent,flush=True)


def evaluate(out,config,split):
    ingestion=read(out/"ingestion.json")
    if ingestion["input_sha256"]!=locked_inputs():
        raise ValueError("Inputs/code changed after ingestion")
    if (out/f"{split}_traces.jsonl").exists():
        raise ValueError("Trace already exists; do not silently overwrite test/dev results")
    if split=="test":
        selection=read(out/"selection_before_test.json")
        if selection["input_sha256"]!=locked_inputs():
            raise ValueError("Configuration changed after selection")
        if selection["dev_trace_sha256"]!=sha(out/"dev_traces.jsonl"):
            raise ValueError("Dev trace changed after selection")
    questions=[q for q in read(ROOT/"benchmark/questions.json") if q["split"]==split]
    encoder,load_seconds=model(config)
    # Only the question text goes to the embedder; gold is used after retrieval.
    started=time.perf_counter()
    vectors=encoder.embed_queries([q["question"] for q in questions])
    query_seconds=time.perf_counter()-started
    query_tokens=dict(encoder.last_stats)
    db=store(config)
    traces=[]
    try:
        for name in ("A","B","C"):
            for q,vector in zip(questions,vectors):
                filters=q.get("filter",{}) if name=="C" else {}
                started=time.perf_counter()
                hits=db.search(name,vector,top_k=3,filters=filters)
                seconds=time.perf_counter()-started
                trace=evaluate_query(q,hits)
                trace.update({"strategy":name,"applied_filter":filters,"search_seconds":seconds})
                traces.append(trace)
                print(split,name,q["id"],"Hit@1",int(trace["hit1"]),"Hit@3",int(trace["hit3"]),flush=True)
    finally:
        db.close()
    jsonl(out/f"{split}_traces.jsonl",traces)
    summary=summarize(traces)
    save(out/f"{split}_metrics.json",{**summary,"query_embedding_seconds":query_seconds,
         "query_embedding_tokens":query_tokens,"model_load_seconds":load_seconds,
         "query_vectors_reused_across_strategies":True,"api_cost_usd":0,"completed_at":now()})
    if split=="dev":
        candidates=summary["groups"]
        counts={name:ingestion["strategies"][name]["chunks"] for name in ("A","B","C")}
        choice=sorted(candidates,key=lambda g:(-g["hit3"],-g["hit1"],counts[g["strategy"]],g["strategy"]))[0]
        save(out/"selection_before_test.json",{"selected_strategy":choice["strategy"],"selected_at":now(),
             "selection_rule":read(ROOT/"benchmark/protocol.json")["selection_rule"],
             "dev_metrics":candidates,"input_sha256":locked_inputs(),
             "dev_trace_sha256":sha(out/"dev_traces.jsonl"),"test_retrieval_seen":False})
        print("Selected on dev before test:",choice["strategy"],flush=True)
    else:
        save(out/"test_completion.json",{"completed_at":now(),"selected_strategy":selection["selected_strategy"],
             "input_sha256":locked_inputs(),"test_trace_sha256":sha(out/"test_traces.jsonl"),
             "no_test_based_tuning":True})
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["ingest","dev","test"])
    parser.add_argument("--results-dir",default="results/benchmark")
    args=parser.parse_args()
    out=(ROOT/args.results_dir).resolve()
    if not out.is_relative_to((ROOT/"results").resolve()):
        parser.error("Results must stay under project/results")
    out.mkdir(parents=True,exist_ok=True)
    load_dotenv(ROOT/"starter/.env",override=False)
    try:
        verify_freeze()
        config=read(ROOT/"artifacts/run_config.json")
        if args.phase=="ingest":
            ingest(out,config)
        else:
            evaluate(out,config,args.phase)
    except Exception as exc:
        message=str(exc)
        if os.environ.get("DATABASE_URL"):
            message=message.replace(os.environ["DATABASE_URL"],"[DATABASE_URL]")
        with (out/"errors.jsonl").open("a",encoding="utf-8") as stream:
            stream.write(json.dumps({"at":now(),"phase":args.phase,"error":type(exc).__name__,"message":message[:500]},ensure_ascii=False)+"\n")
        raise SystemExit(f"{type(exc).__name__}: {message[:250]}") from None


if __name__=="__main__":
    main()
