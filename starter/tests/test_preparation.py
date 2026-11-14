"""Check traceability, no lost content, error visibility and frozen benchmark inputs."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

STARTER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STARTER))
from src.chunking import fixed_size, by_paragraph
from src.ingestion import load_pdf, normalize_text
from src.models import DocumentPage

spec=importlib.util.spec_from_file_location("prepare",STARTER/"scripts/prepare.py")
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class IngestionTests(unittest.TestCase):
    def test_unicode_normalization_preserves_paragraphs_and_meaning(self):
        text="  A\u00a0  con\ufb01dent  answer\r\n\r\nB\tline\u00ad\u200b. "
        normalized=normalize_text(text)
        self.assertEqual(normalized,"A confident answer\n\nB line.")
        self.assertEqual(normalize_text(normalized),normalized)

    @patch("src.ingestion.PdfReader")
    def test_empty_and_failed_pages_keep_physical_numbers(self,reader):
        pages=[Mock(),Mock(),Mock()]
        pages[0].extract_text.return_value="First text"
        pages[1].extract_text.return_value=""
        pages[2].extract_text.side_effect=ValueError("broken page")
        reader.return_value.is_encrypted=False
        reader.return_value.pages=pages
        errors=[]
        actual=load_pdf(Path("sample.pdf"),"doc","source",errors)
        self.assertEqual([p.page for p in actual],[1,2,3])
        self.assertEqual([p.metadata["extraction_status"] for p in actual],["ok","empty","extraction_error"])
        self.assertEqual([e["event"] for e in errors],["empty_page","page_error"])

    @patch("src.ingestion.PdfReader",side_effect=OSError("missing file"))
    def test_unreadable_file_fails_instead_of_mocking(self,reader):
        errors=[]
        with self.assertRaises(ValueError):
            load_pdf(Path("missing.pdf"),"doc","source",errors)
        self.assertEqual(errors[0]["event"],"file_error")


class ChunkTests(unittest.TestCase):
    def page(self,text,number=5):
        return DocumentPage("doc","source",number,text,{"document_part":"main_body","printed_page":1})

    def assert_preserved(self,page,chunks,limit):
        coverage=set()
        for chunk in chunks:
            start,end=chunk.metadata["char_start"],chunk.metadata["char_end"]
            self.assertEqual(chunk.text,page.text[start:end])
            self.assertLessEqual(len(chunk.text),limit)
            self.assertEqual((chunk.document_id,chunk.source,chunk.page),("doc","source",page.page))
            self.assertEqual(chunk.metadata["document_part"],"main_body")
            coverage.update(range(start,end))
        self.assertTrue(all(i in coverage for i,ch in enumerate(page.text) if not ch.isspace()))

    def test_fixed_overlap_tail_coverage_and_metadata(self):
        page=self.page("0123456789abcdefghijk")
        chunks=fixed_size(page,10,3)
        self.assertEqual([c.metadata["char_start"] for c in chunks],[0,7,14])
        self.assert_preserved(page,chunks,10)
        self.assertNotIn("char_start",page.metadata)

    def test_paragraphs_headings_and_oversized_blocks_preserve_content(self):
        page=self.page("# Section one\n\n"+"A complete sentence. "*35+"\n\n# Section two\nAnother thought.")
        chunks=by_paragraph(page,95)
        self.assertGreater(len(chunks),2)
        self.assert_preserved(page,chunks,95)
        self.assertFalse(any("Section one" in c.text and "Section two" in c.text for c in chunks))

    def test_short_heading_chain_and_list_keep_context(self):
        page=self.page("A.1. Governance\nA.1.1. Overview\nA short explanation.\n• Education\n• Monitoring\n• Data retention")
        chunks=by_paragraph(page,300)
        self.assertEqual(len(chunks),1)
        self.assert_preserved(page,chunks,300)

    def test_no_word_boundary_does_not_hang_or_drop_text(self):
        page=self.page("x"*507)
        self.assert_preserved(page,by_paragraph(page,80),80)

    def test_ids_are_stable_but_distinguish_pages_and_edits(self):
        page=self.page("A useful paragraph.")
        one=by_paragraph(page,100)
        self.assertEqual(one,by_paragraph(page,100))
        self.assertNotEqual(one[0].chunk_id,by_paragraph(self.page(page.text,6),100)[0].chunk_id)
        self.assertNotEqual(one[0].chunk_id,by_paragraph(self.page(page.text+" Extra."),100)[0].chunk_id)

    def test_invalid_parameters_fail(self):
        for size,overlap in [(0,0),(10,10),(10,-1),(10,True)]:
            with self.subTest(size=size,overlap=overlap),self.assertRaises(ValueError):
                fixed_size(self.page("text"),size,overlap)
        with self.assertRaises(ValueError):
            by_paragraph(self.page("text"),0)

    def test_empty_pages_produce_no_chunks(self):
        for text in (""," \n\t "):
            self.assertEqual(fixed_size(self.page(text),10,1),[])
            self.assertEqual(by_paragraph(self.page(text),10),[])


class BenchmarkTests(unittest.TestCase):
    def test_actual_quotes_split_and_filters_are_valid(self):
        questions,checks=prepare.validate_benchmark()
        self.assertEqual(len(questions),20)
        self.assertEqual(sum(q["split"]=="test" for q in questions),5)
        self.assertEqual(sum(bool(q.get("filter")) for q in questions),4)
        self.assertTrue(all(c["quote_found"] for c in checks))
        prepare.verify_freeze()

    def test_modified_frozen_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"benchmark").mkdir()
            target=root/"questions.json"
            target.write_text("original",encoding="utf-8")
            manifest={"sha256":{"questions.json":prepare.sha(target)}}
            (root/"benchmark/freeze.json").write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(prepare,"ROOT",root):
                prepare.verify_freeze()
                target.write_text("changed",encoding="utf-8")
                with self.assertRaises(ValueError):
                    prepare.verify_freeze()


if __name__=="__main__":
    unittest.main()
