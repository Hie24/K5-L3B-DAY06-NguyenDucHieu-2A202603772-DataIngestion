"""Read PDF pages without losing physical page numbers; record extraction failures."""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from .models import DocumentPage


def normalize_text(text: str) -> str:
    """NFKC removes PDF ligatures; preserve line/paragraph boundaries and punctuation."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_pdf(path: Path, document_id: str, source: str,
             error_log: list[dict] | None = None) -> list[DocumentPage]:
    """Extract all physical pages, including empty/error pages for an honest audit.

    A failed/empty page is not silently dropped or replaced with OCR/mock content.
    The caller decides which pages meet the corpus inclusion rules.
    """
    if not document_id or not source:
        raise ValueError("document_id and source are required")
    events = error_log if error_log is not None else []
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("PDF requires a password")
    except Exception as exc:
        events.append({"event": "file_error", "source": source, "error": type(exc).__name__})
        raise ValueError(f"Cannot read PDF: {path.name}") from exc
    pages = []
    for number, page in enumerate(reader.pages, 1):
        try:
            raw = page.extract_text() or ""
            text = normalize_text(raw)
            state = "ok" if text else "empty"
            if not text:
                events.append({"event": "empty_page", "page": number, "requires_review": True})
            if "\ufffd" in text:
                events.append({"event": "replacement_character", "page": number,
                               "count": text.count("\ufffd")})
        except Exception as exc:
            raw, text, state = "", "", "extraction_error"
            events.append({"event": "page_error", "page": number, "error": type(exc).__name__})
        pages.append(DocumentPage(document_id, source, number, text, {
            "page_id": f"{document_id}:p{number:03d}",
            "raw_chars": len(raw), "extraction_status": state,
        }))
    return pages
