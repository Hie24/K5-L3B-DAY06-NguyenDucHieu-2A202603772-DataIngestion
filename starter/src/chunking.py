"""Deterministic page-local fixed windows and structure-aware chunking."""
import hashlib
import json
import re

from .models import Chunk, DocumentPage

STRUCTURE = re.compile(
    r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+[A-Z]|"
    r"Appendix\s+[A-Z]\.|A\.\d+(?:\.\d+)*\.?\s+|"
    r"(?:GOVERN|MAP|MEASURE|MANAGE)\s+\d|"
    r"(?:GV|MP|MS|MG)-\d+\.\d+-\d+|"
    r"AI Actor Tasks:|Trustworthy AI Characteristics?:)"
)


def _positive_integer(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end-1].isspace():
        end -= 1
    return start, end


def _make_chunk(page, start, end, method, parameters):
    start, end = _trim(page.text, start, end)
    text = page.text[start:end]
    identity = json.dumps([page.document_id, page.source, page.page, start, end,
                           method, parameters, text], ensure_ascii=False, sort_keys=True)
    chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    metadata = {**page.metadata, "char_start": start, "char_end": end,
                "chunking": method, "parameters": dict(parameters)}
    return Chunk(chunk_id, page.document_id, page.source, page.page, text, metadata)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Page-local windows; no duplicate terminal window; offsets refer to page.text."""
    _positive_integer(size, "size")
    if type(overlap) is not int or not 0 <= overlap < size:
        raise ValueError("overlap must be an integer in [0, size)")
    result = []
    start = 0
    while start < len(page.text):
        end = min(start + size, len(page.text))
        chunk = _make_chunk(page, start, end, "fixed_size", {"size":size,"overlap":overlap})
        if chunk.text:
            result.append(chunk)
        if end == len(page.text):
            break
        start = end - overlap
    return result


def _blocks(text):
    """Use blank lines, numbered headings, action rows and sentence-ending lines.

    PDF soft line wraps are not assumed to be paragraphs. This is a reproducible
    heuristic over extracted text, not reconstruction of PDF table cells.
    """
    boundaries = {0, len(text)}
    for match in re.finditer(r"\n[ \t]*\n+", text):
        boundaries.add(match.end())
    for match in re.finditer(r"(?m)^.*$", text):
        if STRUCTURE.match(match.group()):
            boundaries.add(match.start())
    for match in re.finditer(r"(?m)^[•*]\s+", text):
        boundaries.add(match.start())
    for match in re.finditer(r'[.!?][”"\)]?\n(?=[A-Z“"•])', text):
        boundaries.add(match.end())
    points = sorted(boundaries)
    return [_trim(text,a,b) for a,b in zip(points,points[1:])
            if text[a:b].strip()]


def _split_large(text, start, end, maximum):
    while end - start > maximum:
        candidate = start + maximum
        window = text[start:candidate]
        sentence_ends = [m.end() for m in re.finditer(r'[.!?][”"\)]?\s+',window)]
        word_ends = [m.start() for m in re.finditer(r"\s+",window)]
        useful = [n for n in sentence_ends if n >= maximum//3]
        if not useful:
            useful = [n for n in word_ends if n >= maximum//3]
        cut = start + useful[-1] if useful else candidate
        yield _trim(text,start,cut)
        start = cut
        while start < end and text[start].isspace():
            start += 1
    if start < end:
        yield _trim(text,start,end)


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Greedy pack logical blocks, preserving boundaries and a strict char budget."""
    _positive_integer(max_size, "max_size")
    result, pending = [], None
    parameters = {"max_size":max_size,"overlap":0}
    for start,end in _blocks(page.text):
        new_structure = bool(STRUCTURE.match(page.text[start:end].splitlines()[0]))
        if pending and (end - pending[0] > max_size or new_structure):
            prefix = page.text[pending[0]:pending[1]]
            headings_only = all(STRUCTURE.match(line) for line in prefix.splitlines() if line.strip())
            if headings_only and len(prefix) < 200:
                # A short heading chain belongs with its following paragraph.
                start = pending[0]
            else:
                result.append(_make_chunk(page,*pending,"by_paragraph",parameters))
            pending = None
        if end-start > max_size:
            for a,b in _split_large(page.text,start,end,max_size):
                result.append(_make_chunk(page,a,b,"by_paragraph",parameters))
        elif pending:
            pending = (pending[0],end)
        else:
            pending = (start,end)
    if pending:
        result.append(_make_chunk(page,*pending,"by_paragraph",parameters))
    return [chunk for chunk in result if chunk.text]
