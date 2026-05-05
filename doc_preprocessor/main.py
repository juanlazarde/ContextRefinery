"""Pipeline orchestration and CLI."""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, replace
import difflib
import hashlib
import json
import logging
from pathlib import Path
from time import perf_counter
from typing import Any

from .chunk import Chunk, MarkdownChunker
from .clean import CleanResult, DocumentCleaner
from .compress import LLMCompressor
from .deps import GLOBAL_DEP_REGISTRY, DependencyEvent, canonical_package, install_package
from .estimate import TokenEstimator
from .ingest import DocumentIngestor, IngestResult
from .report import PipelineReport

SUPPORTED_EXTS = {".md", ".txt", ".pdf"}


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
    all_artifacts: bool = False
    output_stem: str | None = None
    auto_install_deps: bool = False


@dataclass
class PipelineResult:
    input_path: Path
    ingest_result: IngestResult
    clean_result: CleanResult
    chunks: list[Chunk]
    report: PipelineReport
    written_files: list[Path]


@dataclass
class BatchOptions:
    input_dir: Path | None = None
    pattern: str = "**/*"
    recursive: bool = True
    workers: int | None = None
    continue_on_error: bool = True
    ordered_results: bool = True
    max_file_mb: int | None = 100


@dataclass
class FileFailure:
    path: Path
    error: str
    dependency_events: list[dict] | None = None


@dataclass
class BatchResult:
    total_files: int
    succeeded: int
    failed: int
    results: list[PipelineResult | FileFailure]
    duration_ms: int
    files_per_sec: float


def run_pipeline(input_path: Path, options: PipelineOptions) -> PipelineResult:
    logger = logging.getLogger("doc_preprocessor")
    logger.setLevel(getattr(logging, options.log_level.upper(), logging.INFO))
    processing_log: list[str] = []

    t0 = perf_counter()
    ingestor = DocumentIngestor(logger=logger)
    ingest = ingestor.load(input_path)
    extracted_tokens = TokenEstimator.estimate(ingest.text)
    logger.info(
        "ingestion: format=%s backend=%s extracted_tokens=%d",
        ingest.source_format,
        ingest.extraction_backend,
        extracted_tokens,
    )
    processing_log.append(
        f"ingestion format={ingest.source_format} backend={ingest.extraction_backend} extracted_tokens={extracted_tokens}"
    )
    t1 = perf_counter()

    cleaner = DocumentCleaner(aggressive=options.aggressive_clean)
    clean_res = cleaner.clean(ingest.text)
    cleaned_tokens = TokenEstimator.estimate(clean_res.cleaned_text)
    logger.info("cleaning: cleaned_tokens=%d", cleaned_tokens)
    processing_log.append(f"cleaning cleaned_tokens={cleaned_tokens}")
    t2 = perf_counter()

    # Always generate chunks for logic correctness.
    chunker = MarkdownChunker(max_chunk_tokens=options.max_chunk_tokens)
    chunks = chunker.chunk(clean_res.cleaned_text)
    logger.info("chunking: chunks=%d", len(chunks))
    processing_log.append(f"chunking chunks={len(chunks)}")
    t3 = perf_counter()

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
        processing_log.append(f"compression pre={pre_comp} post={post_comp}")
    t4 = perf_counter()

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
        processing_log=processing_log,
        timings_ms={},
        dependency_events=[],
        pre_compression_tokens=pre_comp,
        post_compression_tokens=post_comp,
        compression_ratio_actual=ratio_actual,
    )

    written_files: list[Path] = []
    write_start = perf_counter()
    if not options.dry_run:
        out_dir = options.out_dir or (input_path.parent / "outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = options.output_stem or input_path.stem

        extracted_path = out_dir / f"{stem}.extracted.md"
        cleaned_path = out_dir / f"{stem}.cleaned.md"
        chunks_path = out_dir / f"{stem}.chunks.json"
        report_path = out_dir / f"{stem}.report.json"
        diff_path = out_dir / f"{stem}.diff.md"

        cleaned_path.write_text(clean_res.cleaned_text, encoding="utf-8")
        written_files.append(cleaned_path)
        if options.all_artifacts:
            extracted_path.write_text(ingest.text, encoding="utf-8")
            chunks_path.write_text(
                json.dumps([ch.to_dict() for ch in chunks], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            diff_path.write_text(
                _build_diff_markdown(ingest.text, clean_res.cleaned_text),
                encoding="utf-8",
            )
            written_files.extend([extracted_path, chunks_path, diff_path])
        logger.info("output: wrote %d files", len(written_files))
    t5 = perf_counter()

    report.timings_ms = {
        "ingest": round((t1 - t0) * 1000.0, 3),
        "clean": round((t2 - t1) * 1000.0, 3),
        "chunk": round((t3 - t2) * 1000.0, 3),
        "compress": round((t4 - t3) * 1000.0, 3),
        "output": round((t5 - write_start) * 1000.0, 3),
        "total": round((t5 - t0) * 1000.0, 3),
    }
    report.processing_log = processing_log + [
        (
            "timings_ms "
            f"ingest={report.timings_ms['ingest']} clean={report.timings_ms['clean']} "
            f"chunk={report.timings_ms['chunk']} compress={report.timings_ms['compress']} "
            f"output={report.timings_ms['output']} total={report.timings_ms['total']}"
        )
    ]
    if not options.dry_run and options.all_artifacts:
        out_dir = options.out_dir or (input_path.parent / "outputs")
        stem = options.output_stem or input_path.stem
        report_path = out_dir / f"{stem}.report.json"
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written_files.append(report_path)

    logger.info(
        "timings_ms: ingest=%.2f clean=%.2f chunk=%.2f compress=%.2f output=%.2f total=%.2f",
        (t1 - t0) * 1000.0,
        (t2 - t1) * 1000.0,
        (t3 - t2) * 1000.0,
        (t4 - t3) * 1000.0,
        (t5 - write_start) * 1000.0,
        (t5 - t0) * 1000.0,
    )

    return PipelineResult(
        input_path=input_path,
        ingest_result=ingest,
        clean_result=clean_res,
        chunks=chunks,
        report=report,
        written_files=written_files,
    )


def run_pipeline_batch(
    input_paths: list[Path],
    options: PipelineOptions,
    batch_options: BatchOptions,
) -> BatchResult:
    logger = logging.getLogger("doc_preprocessor")
    workers = _normalize_workers(batch_options.workers)

    if options.compress and workers > 2:
        logger.warning("Compression is memory intensive; consider reducing workers")

    sorted_paths = sorted(input_paths, key=lambda p: str(p)) if batch_options.ordered_results else list(input_paths)
    total = len(sorted_paths)
    t0 = perf_counter()

    output_stems = _compute_output_stems(sorted_paths, batch_options.input_dir)

    results_by_path: dict[Path, PipelineResult | FileFailure] = {}
    stop = False
    fail_fast_msg = "Skipped due to fail-fast after prior failure"

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending: dict[Future[Any], Path] = {}
        all_futures: dict[Future[Any], Path] = {}
        idx = 0

        def submit_next() -> bool:
            nonlocal idx
            if idx >= total:
                return False
            path = sorted_paths[idx]
            idx += 1
            per_file_out_dir, out_stem = _compute_output_target(path, batch_options.input_dir, options.out_dir, output_stems[path])
            per_file_opts = replace(
                options,
                out_dir=per_file_out_dir,
                output_stem=out_stem,
            )
            future = executor.submit(_run_file_task, path, per_file_opts, batch_options.max_file_mb)
            pending[future] = path
            all_futures[future] = path
            return True

        for _ in range(min(workers, total)):
            if not submit_next():
                break

        while pending:
            done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                path = pending.pop(fut)
                try:
                    result = fut.result()
                except Exception as exc:  # pragma: no cover
                    result = FileFailure(path=path, error=str(exc))

                results_by_path[path] = result

                if isinstance(result, FileFailure) and not batch_options.continue_on_error:
                    stop = True

            if stop:
                for fut in pending:
                    fut.cancel()
                pending.clear()
                break

            while len(pending) < workers and idx < total:
                submit_next()

        # Best-effort fail-fast: collect any completed running tasks.
        for fut, path in all_futures.items():
            if path in results_by_path or fut.cancelled() or not fut.done():
                continue
            try:
                results_by_path[path] = fut.result()
            except Exception as exc:  # pragma: no cover
                results_by_path[path] = FileFailure(path=path, error=str(exc))

    # Ensure accounting is complete: every discovered input gets a terminal result.
    for p in sorted_paths:
        if p not in results_by_path:
            if stop and not batch_options.continue_on_error:
                results_by_path[p] = FileFailure(path=p, error=fail_fast_msg, dependency_events=[])
            else:
                results_by_path[p] = FileFailure(
                    path=p,
                    error="No result recorded for file (internal batch scheduling gap)",
                    dependency_events=[],
                )

    ordered_results = [results_by_path[p] for p in sorted_paths]
    succeeded = sum(1 for r in ordered_results if isinstance(r, PipelineResult))
    failed = sum(1 for r in ordered_results if isinstance(r, FileFailure))

    duration_ms = int((perf_counter() - t0) * 1000)
    files_per_sec = (succeeded / (duration_ms / 1000.0)) if duration_ms > 0 else float(succeeded)

    return BatchResult(
        total_files=total,
        succeeded=succeeded,
        failed=failed,
        results=ordered_results,
        duration_ms=duration_ms,
        files_per_sec=round(files_per_sec, 4),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic document preprocessing pipeline")
    parser.add_argument(
        "input_paths",
        type=Path,
        nargs="*",
        help="One or more input files (.md, .txt, .pdf). If multiple are given, batch mode is used.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory to scan for batch processing.",
    )
    parser.add_argument(
        "--pattern",
        default="**/*",
        help='Glob pattern for --input-dir discovery (default: "**/*").',
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of batch worker threads (default: auto).",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Best-effort early stop on first failure in batch mode.",
    )
    parser.add_argument(
        "--max-file-mb",
        type=int,
        default=100,
        help="Maximum input file size in MB before rejecting a file (batch mode).",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Enable per-chunk LLMLingua compression.",
    )
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=None,
        help="Target token budget used for compression.",
    )
    parser.add_argument(
        "--compression-ratio",
        type=float,
        default=None,
        help="Compression ratio hint for LLMLingua.",
    )
    parser.add_argument(
        "--max-chunk-tokens",
        type=int,
        default=None,
        help="Maximum tokens per chunk; large sections are split at safe boundaries.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without writing output files.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging verbosity (e.g., DEBUG, INFO, WARNING).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: outputs/ next to input or cwd in batch explicit mode).",
    )
    parser.add_argument(
        "--aggressive-clean",
        action="store_true",
        help="Use more aggressive deterministic cleaning rules.",
    )
    parser.add_argument(
        "--auto-install-deps",
        action="store_true",
        help="Opt in to allowlisted dependency auto-install and one retry.",
    )
    parser.add_argument(
        "--no-auto-install-deps",
        action="store_true",
        help="Hard-disable dependency auto-install (CI-safe).",
    )
    parser.add_argument(
        "--all-artifacts",
        action="store_true",
        help="Write extracted/chunks/report files in addition to cleaned markdown.",
    )
    return parser


def cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.input_dir is not None and args.input_paths:
        print("Invalid input: use either positional paths or --input-dir")
        return 2
    if args.auto_install_deps and args.no_auto_install_deps:
        print("Cannot use --auto-install-deps and --no-auto-install-deps together.")
        return 2

    input_paths: list[Path]
    batch_mode = False
    batch_input_dir: Path | None = None

    if args.input_dir is not None:
        batch_mode = True
        batch_input_dir = args.input_dir
        input_paths = _discover_input_paths(args.input_dir, args.pattern)
    else:
        input_paths = list(args.input_paths)
        if len(input_paths) == 0:
            print("Invalid input: provide at least one input path or --input-dir")
            return 2
        if any(p.suffix.lower() not in SUPPORTED_EXTS for p in input_paths):
            print("Invalid input: supported extensions are .md, .txt, .pdf")
            return 2
        if len(input_paths) > 1:
            batch_mode = True

    if not input_paths:
        print("No supported input files found")
        return 2

    all_artifacts = bool(args.all_artifacts)

    options = PipelineOptions(
        compress=args.compress,
        target_tokens=args.target_tokens,
        compression_ratio=args.compression_ratio,
        max_chunk_tokens=args.max_chunk_tokens,
        dry_run=args.dry_run,
        out_dir=args.out_dir,
        log_level=args.log_level,
        aggressive_clean=args.aggressive_clean,
        all_artifacts=all_artifacts,
        auto_install_deps=(args.auto_install_deps and not args.no_auto_install_deps),
    )

    if not batch_mode:
        single_result = _run_file_task(input_paths[0], options, args.max_file_mb)
        if isinstance(single_result, FileFailure):
            print(single_result.error)
            return 1
        _print_single_summary(single_result, args.dry_run)
        return 0

    batch_options = BatchOptions(
        input_dir=batch_input_dir,
        pattern=args.pattern,
        recursive=True,
        workers=args.workers,
        continue_on_error=not args.fail_fast,
        ordered_results=True,
        max_file_mb=args.max_file_mb,
    )

    batch_result = run_pipeline_batch(input_paths, options, batch_options)
    _write_batch_report(batch_result, options, batch_input_dir)
    _print_batch_summary(batch_result, args.fail_fast)

    if batch_result.failed > 0:
        return 1
    return 0


def _run_file_task(path: Path, options: PipelineOptions, max_file_mb: int | None) -> PipelineResult | FileFailure:
    try:
        if max_file_mb is not None:
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > max_file_mb:
                return FileFailure(path=path, error=f"File exceeds max_file_mb={max_file_mb}", dependency_events=[])
        return _run_with_dependency_healing(path, options)
    except Exception as exc:
        return FileFailure(path=path, error=str(exc), dependency_events=[])


def _discover_input_paths(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(
        [
            p
            for p in input_dir.glob(pattern)
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ],
        key=lambda p: str(p),
    )


def _normalize_workers(workers: int | None) -> int:
    if workers is None or workers <= 0:
        return 4
    return workers


def _compute_output_stems(paths: list[Path], input_dir: Path | None) -> dict[Path, str]:
    stem_counts: dict[str, int] = {}
    for p in paths:
        ext_token = p.suffix.lower().lstrip(".") or "noext"
        candidate = f"{p.stem}__{ext_token}"
        stem_counts[candidate] = stem_counts.get(candidate, 0) + 1

    out: dict[Path, str] = {}
    for p in paths:
        ext_token = p.suffix.lower().lstrip(".") or "noext"
        candidate = f"{p.stem}__{ext_token}"
        if stem_counts[candidate] == 1:
            out[p] = candidate
            continue
        path_hash = hashlib.sha1(str(p.resolve()).encode("utf-8")).hexdigest()[:8]
        out[p] = f"{candidate}__{path_hash}"
    return out


def _compute_output_target(
    path: Path,
    input_dir: Path | None,
    out_dir: Path | None,
    output_stem: str,
) -> tuple[Path, str]:
    root_out = out_dir or Path("outputs")
    if input_dir is None:
        return root_out, output_stem
    rel_parent = path.relative_to(input_dir).parent
    return root_out / rel_parent, output_stem


def _write_batch_report(batch_result: BatchResult, options: PipelineOptions, input_dir: Path | None) -> None:
    if options.dry_run:
        return

    out_root = options.out_dir or (input_dir / "outputs" if input_dir else Path("outputs"))
    out_root.mkdir(parents=True, exist_ok=True)
    report_path = out_root / "batch_report.json"

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for item in batch_result.results:
        if isinstance(item, FileFailure):
            failures.append({"input_path": str(item.path), "error": item.error})
            rows.append(
                {
                    "input_path": str(item.path),
                    "cleaned_output_path": None,
                    "status": "failed",
                    "cleaned_tokens": None,
                    "cleaning_reduction_percent": None,
                    "error": item.error,
                    "dependency_events": item.dependency_events or [],
                }
            )
            continue

        cleaned_path = next((p for p in item.written_files if p.name.endswith(".cleaned.md")), None)
        rows.append(
                {
                    "input_path": str(item.input_path),
                    "cleaned_output_path": str(cleaned_path) if cleaned_path else None,
                "status": "success",
                "cleaned_tokens": item.report.cleaned_tokens,
                "cleaning_reduction_percent": item.report.cleaning_reduction_percent,
                "error": None,
                "dependency_events": item.report.dependency_events,
            }
        )

    payload = {
        "total_files": batch_result.total_files,
        "succeeded": batch_result.succeeded,
        "failed": batch_result.failed,
        "duration_ms": batch_result.duration_ms,
        "files_per_sec": batch_result.files_per_sec,
        "failures": failures,
        "results": rows,
    }
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _print_single_summary(result: PipelineResult, dry_run: bool) -> None:
    extracted_tokens = result.report.extracted_tokens
    cleaned_tokens = result.report.cleaned_tokens
    compressed_tokens = result.report.compressed_tokens

    print(f"Extracted tokens: {extracted_tokens}")
    print(f"Cleaned tokens: {cleaned_tokens}")
    print(f"Cleaning reduction: {result.report.cleaning_reduction_percent:.2f}%")
    if compressed_tokens is not None:
        print(f"Compressed tokens: {compressed_tokens}")
        print(f"Total reduction: {result.report.total_reduction_percent:.2f}%")

    if dry_run:
        print("Dry-run: no files written")
    else:
        print("Artifacts written:")
        for p in result.written_files:
            print(f" - {p}")


def _print_batch_summary(result: BatchResult, fail_fast: bool) -> None:
    print(f"Batch total: {result.total_files}")
    print(f"Succeeded: {result.succeeded}")
    print(f"Failed: {result.failed}")
    print(f"Duration (ms): {result.duration_ms}")
    print(f"Files/sec: {result.files_per_sec}")
    if fail_fast:
        print("Fail-fast mode is best effort: running tasks may complete.")


def _percent_reduction(before: int, after: int | None) -> float | None:
    if after is None:
        return None
    if before <= 0:
        return 0.0
    return round(((before - after) / before) * 100.0, 4)


def _build_diff_markdown(before: str, after: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="extracted",
            tofile="cleaned",
            lineterm="",
        )
    )
    if not diff_lines:
        return "# Diff\n\nNo changes detected.\n"
    return "# Diff\n\n```diff\n" + "\n".join(diff_lines) + "\n```\n"


def _run_with_dependency_healing(path: Path, options: PipelineOptions) -> PipelineResult | FileFailure:
    events: list[DependencyEvent] = []
    try:
        result = run_pipeline(path, options)
        return result
    except Exception as exc:
        dep_key = _dependency_key_from_error(str(exc), options.compress)
        if dep_key is None:
            return FileFailure(path=path, error=str(exc), dependency_events=[])
        package = canonical_package(dep_key)
        if package is None:
            return FileFailure(path=path, error=str(exc), dependency_events=[])
        if not options.auto_install_deps:
            return FileFailure(
                path=path,
                error=_dependency_fallback_message(dep_key),
                dependency_events=[],
            )

        event = install_package(
            package=package,
            reason=f"missing dependency: {dep_key}",
            dry_run=options.dry_run,
            registry=GLOBAL_DEP_REGISTRY,
        )
        event.retry_attempted = True
        if options.dry_run:
            event.retry_succeeded = False
            events.append(event)
            return FileFailure(
                path=path,
                error=_dependency_fallback_message(dep_key),
                dependency_events=[e.to_dict() for e in events],
            )
        if not event.success:
            event.retry_succeeded = False
            events.append(event)
            return FileFailure(
                path=path,
                error=_dependency_fallback_message(dep_key),
                dependency_events=[e.to_dict() for e in events],
            )

        try:
            result = run_pipeline(path, options)
            event.retry_succeeded = True
            events.append(event)
            result.report.dependency_events.extend([e.to_dict() for e in events])
            result.report.processing_log.append(
                f"dependency_remediation package={event.package} success={event.success} retry_succeeded={event.retry_succeeded}"
            )
            return result
        except Exception as retry_exc:
            event.retry_succeeded = False
            events.append(event)
            return FileFailure(
                path=path,
                error=str(retry_exc),
                dependency_events=[e.to_dict() for e in events],
            )


def _dependency_key_from_error(error: str, compress_enabled: bool) -> str | None:
    e = error.lower()
    if "pdf support requires markitdown or pymupdf" in e:
        return "markitdown"
    if "llmlingua not installed" in e and compress_enabled:
        return "llmlingua"
    if "no module named 'fitz'" in e:
        return "fitz"
    if "no module named 'markitdown'" in e:
        return "markitdown"
    if "no module named 'llmlingua'" in e and compress_enabled:
        return "llmlingua"
    return None


def _dependency_fallback_message(dep_key: str) -> str:
    if dep_key in {"markitdown", "fitz", "pymupdf"}:
        return (
            "PDF support requires MarkItDown or PyMuPDF.\n"
            "Install with:\n"
            "pip install markitdown pymupdf\n\n"
            "Or rerun with:\n"
            "--auto-install-deps"
        )
    if dep_key == "llmlingua":
        return (
            "LLMLingua is required for --compress.\n"
            "Install with:\n"
            "pip install llmlingua\n\n"
            "Or rerun with:\n"
            "--auto-install-deps"
        )
    return dep_key


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
