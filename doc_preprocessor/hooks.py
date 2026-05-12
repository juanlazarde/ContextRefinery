"""Pre-run preprocessing hook for skill workflows."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from time import strftime
from typing import Any
import uuid

from .main import (
    BatchOptions,
    BatchResult,
    FileFailure,
    PipelineOptions,
    PipelineResult,
    SUPPORTED_EXTS,
    run_pipeline_batch,
)

GENERATED_SUFFIXES = (
    ".cleaned.md",
    ".chunks.json",
    ".report.json",
    ".extracted.md",
    ".diff.md",
)
GENERATED_FILENAMES = {"batch_report.json", "hook_summary.json"}


@dataclass
class SkillPreRunOptions:
    out_dir: Path | None = None
    all_artifacts: bool = False
    compress: bool = False
    target_tokens: int | None = None
    compression_ratio: float | None = None
    max_chunk_tokens: int | None = None
    workers: int | None = None
    fail_fast: bool = False
    max_file_mb: int | None = 100
    require_all_success: bool = False
    pattern: str = "**/*"
    aggressive_clean: bool = False
    auto_install_deps: bool = False
    log_level: str = "INFO"
    dry_run: bool = False


@dataclass
class SkillPreRunResult:
    run_id: str
    summary_path: Path
    cleaned_paths: list[Path]
    failures: list[FileFailure]
    succeeded: int
    failed: int
    artifact_root: Path
    ok: bool


def preprocess_for_skill(
    inputs: list[Path],
    options: SkillPreRunOptions | None = None,
) -> SkillPreRunResult:
    opts = options or SkillPreRunOptions()
    input_paths = [Path(p) for p in inputs]
    run_id = _build_run_id(input_paths, opts)
    artifact_root = opts.out_dir or Path(".doc_preprocessor") / "skill_runs" / run_id
    summary_path = artifact_root / "hook_summary.json"

    processable, discovery_failures, warnings = _classify_inputs(input_paths, opts.pattern)
    processable = sorted(dict.fromkeys(processable), key=lambda p: str(p))

    pipeline_options = PipelineOptions(
        compress=opts.compress,
        target_tokens=opts.target_tokens,
        compression_ratio=opts.compression_ratio,
        max_chunk_tokens=opts.max_chunk_tokens,
        dry_run=opts.dry_run,
        out_dir=artifact_root,
        aggressive_clean=opts.aggressive_clean,
        all_artifacts=opts.all_artifacts,
        auto_install_deps=opts.auto_install_deps,
        log_level=opts.log_level,
    )
    batch_options = BatchOptions(
        input_dir=None,
        pattern=opts.pattern,
        workers=opts.workers,
        continue_on_error=not opts.fail_fast,
        ordered_results=True,
        max_file_mb=opts.max_file_mb,
    )

    batch_result = (
        run_pipeline_batch(processable, pipeline_options, batch_options)
        if processable
        else BatchResult(0, 0, 0, [], 0, 0.0)
    )

    all_failures = discovery_failures + [
        r for r in batch_result.results if isinstance(r, FileFailure)
    ]
    cleaned_paths = _cleaned_paths(batch_result)
    succeeded = batch_result.succeeded
    failed = len(all_failures)
    ok = failed == 0 if opts.require_all_success else succeeded > 0 or failed == 0

    summary = {
        "run_id": run_id,
        "input_count": len(input_paths),
        "succeeded": succeeded,
        "failed": failed,
        "cleaned_paths": [str(p) for p in cleaned_paths],
        "warnings": warnings,
        "failures": [_failure_to_dict(f) for f in all_failures],
        "artifact_root": str(artifact_root),
        "options_used": _options_summary(opts),
    }
    if not opts.dry_run:
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return SkillPreRunResult(
        run_id=run_id,
        summary_path=summary_path,
        cleaned_paths=cleaned_paths,
        failures=all_failures,
        succeeded=succeeded,
        failed=failed,
        artifact_root=artifact_root,
        ok=ok,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocess declared skill inputs before skill execution.")
    parser.add_argument("inputs", type=Path, nargs="*", help="Explicit files or directories to preprocess.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Artifact root for this hook run.")
    parser.add_argument("--pattern", default="**/*", help='Glob pattern used for directory inputs (default: "**/*").')
    parser.add_argument("--workers", type=int, default=None, help="Number of worker threads for batch processing.")
    parser.add_argument("--require-all-success", action="store_true", help="Return failure if any input fails.")
    parser.add_argument("--all-artifacts", action="store_true", help="Write extracted/chunks/report/diff artifacts.")
    parser.add_argument("--compress", action="store_true", help="Enable per-chunk compression.")
    parser.add_argument("--target-tokens", type=int, default=None, help="Target token budget for compression.")
    parser.add_argument("--compression-ratio", type=float, default=None, help="Compression ratio hint.")
    parser.add_argument("--max-chunk-tokens", type=int, default=None, help="Maximum tokens per chunk.")
    parser.add_argument("--max-file-mb", type=int, default=100, help="Maximum file size in MB. Use 0 to reject all non-empty files.")
    parser.add_argument("--fail-fast", action="store_true", help="Best-effort early stop on failure.")
    parser.add_argument("--aggressive-clean", action="store_true", help="Use stronger deterministic cleanup.")
    parser.add_argument("--auto-install-deps", action="store_true", help="Opt in to allowlisted dependency install.")
    parser.add_argument("--no-auto-install-deps", action="store_true", help="Hard-disable dependency auto-install (CI-safe).")
    parser.add_argument("--log-level", default="INFO", help="Logging verbosity (e.g., DEBUG, INFO, WARNING).")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files.")
    return parser


def cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.inputs:
        print("Invalid input: provide at least one file or directory.")
        return 2
    if args.auto_install_deps and args.no_auto_install_deps:
        print("Cannot use --auto-install-deps and --no-auto-install-deps together.")
        return 2

    result = preprocess_for_skill(
        args.inputs,
        SkillPreRunOptions(
            out_dir=args.out_dir,
            all_artifacts=args.all_artifacts,
            compress=args.compress,
            target_tokens=args.target_tokens,
            compression_ratio=args.compression_ratio,
            max_chunk_tokens=args.max_chunk_tokens,
            workers=args.workers,
            fail_fast=args.fail_fast,
            max_file_mb=args.max_file_mb,
            require_all_success=args.require_all_success,
            pattern=args.pattern,
            aggressive_clean=args.aggressive_clean,
            auto_install_deps=(args.auto_install_deps and not args.no_auto_install_deps),
            log_level=args.log_level,
            dry_run=args.dry_run,
        ),
    )
    print(f"Hook run: {result.run_id}")
    print(f"Succeeded: {result.succeeded}")
    print(f"Failed: {result.failed}")
    print(f"Summary: {result.summary_path}")
    return 0 if result.ok else 1


def _classify_inputs(inputs: list[Path], pattern: str) -> tuple[list[Path], list[FileFailure], list[str]]:
    files: list[Path] = []
    failures: list[FileFailure] = []
    warnings: list[str] = []

    for item in inputs:
        if not item.exists():
            failures.append(FileFailure(path=item, error="Input does not exist", dependency_events=[]))
            continue
        if item.is_dir():
            discovered = [
                p for p in item.glob(pattern)
                if p.is_file() and _should_process_file(p)
            ]
            files.extend(discovered)
            if not discovered:
                warnings.append(f"No supported files found in directory: {item}")
            continue
        if item.is_file() and _should_process_file(item):
            files.append(item)
            continue
        warnings.append(f"Skipped generated or unsupported file: {item}")

    return files, failures, warnings


def _should_process_file(path: Path) -> bool:
    parts = set(path.parts)
    if ".doc_preprocessor" in parts:
        return False
    name = path.name
    if name in GENERATED_FILENAMES:
        return False
    if any(name.endswith(suffix) for suffix in GENERATED_SUFFIXES):
        return False
    return path.suffix.lower() in SUPPORTED_EXTS


def _build_run_id(inputs: list[Path], options: SkillPreRunOptions) -> str:
    return f"{strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _cleaned_paths(batch_result: BatchResult) -> list[Path]:
    paths: list[Path] = []
    for item in batch_result.results:
        if not isinstance(item, PipelineResult):
            continue
        paths.extend(p for p in item.written_files if p.name.endswith(".cleaned.md"))
    return paths


def _failure_to_dict(failure: FileFailure) -> dict[str, Any]:
    return {
        "path": str(failure.path),
        "error": failure.error,
        "dependency_events": failure.dependency_events or [],
    }


def _options_summary(options: SkillPreRunOptions) -> dict[str, Any]:
    data = asdict(options)
    data["out_dir"] = str(options.out_dir) if options.out_dir else None
    return data


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
