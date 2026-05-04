"""Pipeline orchestration and CLI."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path

from .chunk import Chunk, MarkdownChunker
from .clean import CleanResult, DocumentCleaner
from .compress import LLMCompressor
from .estimate import TokenEstimator
from .ingest import DocumentIngestor, IngestResult
from .report import PipelineReport


@dataclass
class PipelineOptions:
    compress: bool = False
    target_tokens: int | None = None
    compression_ratio: float | None = None
    max_chunk_tokens: int | None = None
    dry_run: bool = False
    out_dir: Path | None = None
    log_level: str = "INFO"
    aggressive_clean: bool = False


@dataclass
class PipelineResult:
    ingest_result: IngestResult
    clean_result: CleanResult
    chunks: list[Chunk]
    report: PipelineReport
    written_files: list[Path]


def run_pipeline(input_path: Path, options: PipelineOptions) -> PipelineResult:
    logger = logging.getLogger("doc_preprocessor")
    logger.setLevel(getattr(logging, options.log_level.upper(), logging.INFO))

    ingestor = DocumentIngestor(logger=logger)
    ingest = ingestor.load(input_path)
    extracted_tokens = TokenEstimator.estimate(ingest.text)
    logger.info(
        "ingestion: format=%s backend=%s extracted_tokens=%d",
        ingest.source_format,
        ingest.extraction_backend,
        extracted_tokens,
    )

    cleaner = DocumentCleaner(aggressive=options.aggressive_clean)
    clean_res = cleaner.clean(ingest.text)
    cleaned_tokens = TokenEstimator.estimate(clean_res.cleaned_text)
    logger.info("cleaning: cleaned_tokens=%d", cleaned_tokens)

    chunker = MarkdownChunker(max_chunk_tokens=options.max_chunk_tokens)
    chunks = chunker.chunk(clean_res.cleaned_text)
    logger.info("chunking: chunks=%d", len(chunks))

    compressed_tokens = None
    pre_comp = None
    post_comp = None
    ratio_actual = None
    if options.compress:
        compressor = LLMCompressor(
            target_tokens=options.target_tokens,
            compression_ratio=options.compression_ratio,
        )
        chunks, stats = compressor.compress_chunks(chunks)
        compressed_tokens = sum(ch.estimated_tokens for ch in chunks)
        pre_comp = stats.pre_compression_tokens
        post_comp = stats.post_compression_tokens
        ratio_actual = stats.compression_ratio_actual
        logger.info("compression: pre=%d post=%d", pre_comp, post_comp)

    all_warnings = list(ingest.warnings) + chunker.warnings + clean_res.removed.warnings

    cleaning_reduction_percent = _percent_reduction(extracted_tokens, cleaned_tokens)
    total_reduction_percent = (
        _percent_reduction(extracted_tokens, compressed_tokens)
        if compressed_tokens is not None
        else None
    )

    report = PipelineReport(
        source_format=ingest.source_format,
        extraction_backend=ingest.extraction_backend,
        warnings=all_warnings,
        extraction_warnings=ingest.extraction_warnings,
        extracted_chars=ingest.extracted_chars,
        extracted_non_whitespace_chars=ingest.extracted_non_whitespace_chars,
        extracted_pages=ingest.extracted_pages,
        extracted_tokens=extracted_tokens,
        cleaned_tokens=cleaned_tokens,
        compressed_tokens=compressed_tokens,
        cleaning_reduction_percent=cleaning_reduction_percent,
        total_reduction_percent=total_reduction_percent,
        chunks=len(chunks),
        removed=asdict(clean_res.removed),
        pre_compression_tokens=pre_comp,
        post_compression_tokens=post_comp,
        compression_ratio_actual=ratio_actual,
    )

    written_files: list[Path] = []
    if not options.dry_run:
        out_dir = options.out_dir or input_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem

        extracted_path = out_dir / f"{stem}.extracted.md"
        cleaned_path = out_dir / f"{stem}.cleaned.md"
        chunks_path = out_dir / f"{stem}.chunks.json"
        report_path = out_dir / f"{stem}.report.json"

        extracted_path.write_text(ingest.text, encoding="utf-8")
        cleaned_path.write_text(clean_res.cleaned_text, encoding="utf-8")
        chunks_path.write_text(
            json.dumps([ch.to_dict() for ch in chunks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        written_files.extend([extracted_path, cleaned_path, chunks_path, report_path])
        logger.info("output: wrote %d files", len(written_files))

    return PipelineResult(
        ingest_result=ingest,
        clean_result=clean_res,
        chunks=chunks,
        report=report,
        written_files=written_files,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic document preprocessing pipeline")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--compress", action="store_true")
    parser.add_argument("--target_tokens", type=int, default=None)
    parser.add_argument("--compression_ratio", type=float, default=None)
    parser.add_argument("--max-chunk-tokens", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--aggressive-clean", action="store_true")
    return parser


def cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    options = PipelineOptions(
        compress=args.compress,
        target_tokens=args.target_tokens,
        compression_ratio=args.compression_ratio,
        max_chunk_tokens=args.max_chunk_tokens,
        dry_run=args.dry_run,
        out_dir=args.out_dir,
        log_level=args.log_level,
        aggressive_clean=args.aggressive_clean,
    )

    result = run_pipeline(args.input_path, options)
    extracted_tokens = result.report.extracted_tokens
    cleaned_tokens = result.report.cleaned_tokens
    compressed_tokens = result.report.compressed_tokens

    print(f"Extracted tokens: {extracted_tokens}")
    print(f"Cleaned tokens: {cleaned_tokens}")
    print(f"Cleaning reduction: {result.report.cleaning_reduction_percent:.2f}%")
    if compressed_tokens is not None:
        print(f"Compressed tokens: {compressed_tokens}")
        print(f"Total reduction: {result.report.total_reduction_percent:.2f}%")

    if args.dry_run:
        print("Dry-run: no files written")
    else:
        print("Artifacts written:")
        for p in result.written_files:
            print(f" - {p}")

    return 0


def _percent_reduction(before: int, after: int | None) -> float | None:
    if after is None:
        return None
    if before <= 0:
        return 0.0
    return round(((before - after) / before) * 100.0, 4)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
