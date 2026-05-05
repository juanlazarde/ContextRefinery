"""Report models and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineReport:
    source_format: str
    extraction_backend: str
    warnings: list[str]
    extraction_warnings: list[str]
    extracted_chars: int
    extracted_non_whitespace_chars: int
    extracted_pages: int | None
    extracted_tokens: int
    cleaned_tokens: int
    compressed_tokens: int | None
    cleaning_reduction_percent: float | None
    total_reduction_percent: float | None
    chunks: int
    removed: dict
    processing_log: list[str]
    timings_ms: dict
    dependency_events: list[dict]
    pre_compression_tokens: int | None = None
    post_compression_tokens: int | None = None
    compression_ratio_actual: float | None = None

    def to_dict(self) -> dict:
        return {
            "source_format": self.source_format,
            "extraction_backend": self.extraction_backend,
            "warnings": self.warnings,
            "extraction_warnings": self.extraction_warnings,
            "extracted_chars": self.extracted_chars,
            "extracted_non_whitespace_chars": self.extracted_non_whitespace_chars,
            "extracted_pages": self.extracted_pages,
            "extracted_tokens": self.extracted_tokens,
            "cleaned_tokens": self.cleaned_tokens,
            "compressed_tokens": self.compressed_tokens,
            "cleaning_reduction_percent": self.cleaning_reduction_percent,
            "total_reduction_percent": self.total_reduction_percent,
            "chunks": self.chunks,
            "removed": self.removed,
            "processing_log": self.processing_log,
            "timings_ms": self.timings_ms,
            "dependency_events": self.dependency_events,
            "pre_compression_tokens": self.pre_compression_tokens,
            "post_compression_tokens": self.post_compression_tokens,
            "compression_ratio_actual": self.compression_ratio_actual,
        }
