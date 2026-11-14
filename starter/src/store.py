"""Persistent PostgreSQL + pgvector; parameterized exact cosine search."""
import json
import math
from collections import defaultdict
from typing import Any
import psycopg
from psycopg.rows import dict_row
from .models import Chunk


class PgVectorStore:
    def __init__(self,database_url: str,dimensions: int) -> None:
        if type(dimensions) is not int or not 1<=dimensions<=2000:
            raise ValueError("Invalid dimensions")
        self.dimensions=dimensions
        self.conn=psycopg.connect(database_url,autocommit=True,row_factory=dict_row,connect_timeout=10)

    def close(self):
        self.conn.close()

    def create_schema(self) -> None:
        # Only the validated integer dimension enters this DDL; values remain parameters.
        self.conn.execute(f"""CREATE TABLE IF NOT EXISTS lab06_chunks (
            strategy text NOT NULL CHECK(strategy IN ('A','B','C')),
            chunk_id text NOT NULL, document_id text NOT NULL, source text NOT NULL,
            page integer NOT NULL CHECK(page>0), text text NOT NULL,
            metadata jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL,
            PRIMARY KEY(strategy,chunk_id))""")
        actual=self.conn.execute("""SELECT format_type(atttypid,atttypmod) AS type
            FROM pg_attribute WHERE attrelid='lab06_chunks'::regclass
            AND attname='embedding' AND NOT attisdropped""").fetchone()
        if actual["type"]!=f"vector({self.dimensions})":
            raise ValueError("Existing vector column has a different dimension")
        # No HNSW/IVFFlat index: exact similarity search for this small corpus.
        self.conn.execute("CREATE INDEX IF NOT EXISTS lab06_strategy_doc ON lab06_chunks(strategy,document_id)")

    def _vector(self,vector):
        if len(vector)!=self.dimensions or any(not math.isfinite(float(x)) for x in vector):
            raise ValueError("Invalid vector length or values")
        if not any(float(x)!=0 for x in vector):
            raise ValueError("Zero vector is invalid for cosine search")
        return json.dumps([float(x) for x in vector])

    @staticmethod
    def _strategy(strategy):
        if strategy not in ("A","B","C"):
            raise ValueError("Unknown strategy")

    def upsert(self,strategy: str,chunks: list[Chunk],vectors: list[list[float]]) -> None:
        self._strategy(strategy)
        if len(chunks)!=len(vectors):
            raise ValueError("Chunk/vector lengths differ")
        if len({c.chunk_id for c in chunks})!=len(chunks):
            raise ValueError("Duplicate chunk IDs in batch")
        rows,by_doc=[],defaultdict(list)
        for chunk,vector in zip(chunks,vectors):
            if not chunk.document_id or not chunk.source or chunk.page<1 or not chunk.text.strip():
                raise ValueError("Chunk lacks traceable source/text")
            if chunk.metadata.get("document_part") not in ("main_body","appendix_a"):
                raise ValueError("Missing verified document_part")
            rows.append((strategy,chunk.chunk_id,chunk.document_id,chunk.source,chunk.page,
                         chunk.text,json.dumps(chunk.metadata,ensure_ascii=False),self._vector(vector)))
            by_doc[chunk.document_id].append(chunk.chunk_id)
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.executemany("""INSERT INTO lab06_chunks
                    (strategy,chunk_id,document_id,source,page,text,metadata,embedding)
                    VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector)
                    ON CONFLICT(strategy,chunk_id) DO UPDATE SET
                    document_id=EXCLUDED.document_id, source=EXCLUDED.source,page=EXCLUDED.page,
                    text=EXCLUDED.text,metadata=EXCLUDED.metadata,embedding=EXCLUDED.embedding""",rows)
                # This batch is a complete snapshot of each document it contains.
                for document_id,ids in by_doc.items():
                    cur.execute("""DELETE FROM lab06_chunks WHERE strategy=%s AND document_id=%s
                        AND NOT (chunk_id=ANY(%s))""",(strategy,document_id,ids))

    def count(self,strategy):
        self._strategy(strategy)
        return self.conn.execute("SELECT count(*) AS n FROM lab06_chunks WHERE strategy=%s",(strategy,)).fetchone()["n"]

    def search(self,strategy: str,query_vector: list[float],top_k: int=3,
               filters: dict[str,Any] | None=None) -> list[dict[str,Any]]:
        self._strategy(strategy)
        if type(top_k) is not int or not 1<=top_k<=100:
            raise ValueError("Invalid top_k")
        filters=filters or {}
        if set(filters)-{"document_part"}:
            raise ValueError("Only pre-supplied document_part filtering is permitted")
        if filters and filters["document_part"] not in ("main_body","appendix_a"):
            raise ValueError("Invalid filter value")
        rows=self.conn.execute("""SELECT chunk_id,document_id,source,page,text,metadata,
            embedding <=> %s::vector AS distance FROM lab06_chunks
            WHERE strategy=%s AND metadata @> %s::jsonb
            ORDER BY distance,chunk_id LIMIT %s""",
            (self._vector(query_vector),strategy,json.dumps(filters),top_k)).fetchall()
        return [{**row,"score":1-float(row["distance"]),
                 "metadata":{**row["metadata"],"document_id":row["document_id"],
                             "source":row["source"],"page":row["page"]}} for row in rows]
