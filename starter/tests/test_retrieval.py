"""Metric and input-contract tests; synthetic vectors appear only in isolated tests."""
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation import evaluate_query,summarize
from src.store import PgVectorStore
from src.models import Chunk


class MetricTests(unittest.TestCase):
    def question(self):
        return {"id":"q","split":"test","question":"x","expected_answer":"x",
                "gold_source_id":"doc","gold_page":2,"evidence_quote":"The full evidence."}

    def hit(self,text="The full evidence.",page=2):
        return {"document_id":"doc","page":page,"text":text}

    def test_correct_quote_on_wrong_page_is_not_a_hit(self):
        self.assertFalse(evaluate_query(self.question(),[self.hit(page=3)])["hit3"])

    def test_partial_evidence_in_two_chunks_is_not_a_primary_hit(self):
        self.assertFalse(evaluate_query(self.question(),[self.hit("The full"),self.hit("evidence.")])["hit3"])

    def test_hit3_does_not_mean_hit1(self):
        q=evaluate_query(self.question(),[self.hit("Unrelated"),self.hit()])
        self.assertFalse(q["hit1"])
        self.assertTrue(q["hit3"])

    def test_documented_alternative_source_is_accepted(self):
        q=self.question()
        q["gold_evidence"]=[{"source_id":"other","page":4,"evidence_quote":"Another proof."}]
        self.assertTrue(evaluate_query(q,[{"document_id":"other","page":4,"text":"Another\nproof."}])["hit1"])

    def test_summary_keeps_strategy_and_split_denominators(self):
        rows=[{"strategy":"A","split":"dev","hit1":False,"hit3":True},
              {"strategy":"A","split":"test","hit1":False,"hit3":False}]
        groups=summarize(rows)["groups"]
        self.assertEqual([g["total"] for g in groups],[1,1])
        self.assertEqual(groups[0]["hit3_n"],1)

    @patch("src.store.psycopg.connect")
    def test_invalid_vectors_and_gold_filter_are_rejected(self,connect):
        db=PgVectorStore("not-used",3)
        for v in ([1,2],[0,0,0],[1,float("nan"),2]):
            with self.assertRaises(ValueError):
                db.search("A",v)
        with self.assertRaises(ValueError):
            db.search("C",[1,0,0],filters={"gold_page":2})
        connect.return_value.execute.assert_not_called()


@unittest.skipUnless(os.getenv("LAB06_INTEGRATION")=="1","requires real local pgvector")
class RealStoreTests(unittest.TestCase):
    def test_transactional_stale_removal_filters_and_rollback(self):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1]/".env")
        db=PgVectorStore(os.environ["DATABASE_URL"],384)
        db.create_schema()
        before=db.count("A")
        vector=[1.0]+[0.0]*383
        try:
            # Owned temporary test rows are rolled back; never used in the benchmark.
            with db.conn.transaction(force_rollback=True):
                def chunk(cid,text):
                    return Chunk(cid,"__lab06_validation__","isolated unit fixture",1,text,{"document_part":"main_body"})
                db.upsert("A",[chunk("old1","old first"),chunk("old2","old second")],[vector,vector])
                db.upsert("A",[chunk("new1","replacement")],[vector])
                rows=db.conn.execute("SELECT chunk_id FROM lab06_chunks WHERE document_id='__lab06_validation__'").fetchall()
                self.assertEqual([r["chunk_id"] for r in rows],["new1"])
                hits=db.search("A",vector,filters={"document_part":"appendix_a"})
                self.assertTrue(all(h["metadata"]["document_part"]=="appendix_a" for h in hits))
            self.assertEqual(db.count("A"),before)
            n=db.conn.execute("SELECT count(*) AS n FROM lab06_chunks WHERE document_id='__lab06_validation__'").fetchone()["n"]
            self.assertEqual(n,0)
        finally:
            db.close()
