"""Document ingestion for md/txt/pdf sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import importlib
import logging


PDF_DEP_ERROR = (
    "PDF support requires MarkItDown or PyMuPDF. "
    "Install with: pip install markitdown pymupdf"
)


@dataclass
class IngestResult:
    text: str
    source_format: str
    extraction_backend: str
    warnings: list[str] = field(default_factory=list)
    extracted_chars: int = 0
    extracted_non_whitespace_chars: int = 0
    extracted_pages: int | None = None
    extraction_warnings: list[str] = field(default_factory=list)


class DocumentIngestor:
    """Loads document content from supported formats."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

    def load(self, path: Path) -> IngestResult:
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8")
            return self._build_result(text, suffix.lstrip("."), "direct")
        if suffix == ".pdf":
            return self._load_pdf(path)
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .md, .txt, .pdf")

    def _build_result(
        self,
        text: str,
        source_format: str,
        backend: str,
        pages: int | None = None,
    ) -> IngestResult:
        warnings: list[str] = []
        extraction_warnings: list[str] = []
        extracted_chars = len(text)
        non_ws_chars = len("".join(text.split()))
        if source_format == "pdf" and non_ws_chars < 200:
            msg = "PDF may be scanned/image-based. OCR not enabled."
            warnings.append(msg)
            extraction_warnings.append(msg)
        return IngestResult(
            text=text,
            source_format=source_format,
            extraction_backend=backend,
            warnings=warnings,
            extracted_chars=extracted_chars,
            extracted_non_whitespace_chars=non_ws_chars,
            extracted_pages=pages,
            extraction_warnings=extraction_warnings,
        )

    def _load_pdf(self, path: Path) -> IngestResult:
        markitdown_text, markitdown_pages = self._try_markitdown(path)
        if markitdown_text is not None:
            self.logger.info("PDF extracted via MarkItDown")
            return self._build_result(markitdown_text, "pdf", "markitdown", markitdown_pages)

        fitz_text, fitz_pages = self._try_fitz(path)
        if fitz_text is not None:
            self.logger.info("PDF extracted via PyMuPDF")
            return self._build_result(fitz_text, "pdf", "pymupdf", fitz_pages)

        raise RuntimeError(PDF_DEP_ERROR)

    def _try_markitdown(self, path: Path) -> tuple[str | None, int | None]:
        mod = self._import_first(["markitdown", "MarkItDown"])
        if mod is None:
            return None, None

        md_class = getattr(mod, "MarkItDown", None)
        if md_class is None:
            return None, None

        try:
            extractor = md_class()
            result = extractor.convert(str(path))
            text = self._extract_markitdown_text(result)
            if not text:
                return None, None
            pages = self._extract_markitdown_pages(result)
            return text, pages
        except Exception as exc:  # pragma: no cover
            self.logger.warning("MarkItDown extraction failed: %s", exc)
            return None, None

    def _extract_markitdown_text(self, result: Any) -> str:
        for attr in ("text_content", "markdown", "content", "text"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value
        if isinstance(result, str) and result.strip():
            return result
        return ""

    def _extract_markitdown_pages(self, result: Any) -> int | None:
        candidates = [
            getattr(result, "pages", None),
            getattr(result, "page_count", None),
            getattr(getattr(result, "metadata", None), "pages", None),
        ]
        for val in candidates:
            if isinstance(val, int) and val > 0:
                return val
        return None

    def _try_fitz(self, path: Path) -> tuple[str | None, int | None]:
        mod = self._import_first(["fitz"])
        if mod is None:
            return None, None
        try:
            doc = mod.open(str(path))
            pages = len(doc)
            parts: list[str] = []
            for page in doc:
                parts.append(page.get_text("text") or "")
            text = "\n\n".join(parts).strip()
            return (text if text else None), pages
        except Exception as exc:  # pragma: no cover
            self.logger.warning("PyMuPDF extraction failed: %s", exc)
            return None, None

    def _import_first(self, module_names: list[str]):
        for name in module_names:
            try:
                return importlib.import_module(name)
            except Exception:
                continue
        return None
