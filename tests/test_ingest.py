from pathlib import Path
import types

import pytest

from doc_preprocessor.ingest import DocumentIngestor, PDF_DEP_ERROR


class FakeResult:
    def __init__(self, text):
        self.text_content = text


class FakeMarkItDown:
    def convert(self, _path):
        return FakeResult("pdf text")


def test_md_txt_ingestion(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("hello", encoding="utf-8")
    out = DocumentIngestor().load(p)
    assert out.text == "hello"
    assert out.source_format == "md"


def test_pdf_markitdown_path(tmp_path: Path, monkeypatch):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")

    ing = DocumentIngestor()
    monkeypatch.setattr(ing, "_import_first", lambda names: types.SimpleNamespace(MarkItDown=FakeMarkItDown) if "markitdown" in names else None)
    out = ing.load(p)
    assert out.extraction_backend == "markitdown"
    assert out.text == "pdf text"


def test_pdf_fitz_fallback(tmp_path: Path, monkeypatch):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")

    class Page:
        def get_text(self, _mode):
            return "hello"

    class Doc:
        def __iter__(self):
            return iter([Page(), Page()])

        def __len__(self):
            return 2

    fitz_mod = types.SimpleNamespace(open=lambda _p: Doc())

    ing = DocumentIngestor()

    def fake_import(names):
        if names == ["markitdown", "MarkItDown"]:
            return None
        if names == ["fitz"]:
            return fitz_mod
        return None

    monkeypatch.setattr(ing, "_import_first", fake_import)
    out = ing.load(p)
    assert out.extraction_backend == "pymupdf"
    assert out.extracted_pages == 2


def test_pdf_missing_backends_raises(tmp_path: Path, monkeypatch):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")
    ing = DocumentIngestor()
    monkeypatch.setattr(ing, "_import_first", lambda names: None)
    with pytest.raises(RuntimeError, match=PDF_DEP_ERROR):
        ing.load(p)
