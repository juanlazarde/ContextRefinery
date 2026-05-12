# Changelog

## [0.2.0] - 2026-05-12
### Changed
- **Breaking:** Default single-file output directory changed from the input file's parent directory to `<input_parent>/outputs/`. Callers relying on output appearing next to the input must pass `--out-dir` explicitly or set `PipelineOptions(out_dir=...)`.

### Fixed
- `importlib.invalidate_caches()` is now called after a successful `pip install` in dependency auto-healing, so the newly installed package is importable in the same process without restarting.
- `_print_single_summary` no longer crashes with `TypeError` when `cleaning_reduction_percent` or `total_reduction_percent` is `None`.
- `files_per_sec` in `BatchResult` is now `inf` (not the succeeded count) when the batch duration rounds to 0 ms with at least one success.
- `run_pipeline_batch` with `ordered_results=False` now returns results in completion-arrival order rather than input order.
- `get_installed_version("pymupdf")` now correctly imports `fitz` (the PyMuPDF import name) instead of `pymupdf`.
- `_build_run_id` now produces a unique run ID for every call, preventing concurrent or rapid-fire calls from sharing an artifact directory.

### Added
- `conftest.py` autouse fixture resets the global dependency registry between tests, preventing cross-test pollution.
- `install-to-project.sh` now automatically appends `.skill_work/` to the target project's `.gitignore` (idempotent).
- `--max-file-mb 0` behaviour documented in CLI help: 0 rejects all non-empty files.

## [0.1.0] - 2026-05-04
### Added
- Initial deterministic document preprocessing pipeline
- CLI entrypoint (`preprocess.py` and `doc-preprocess`)
- Ingestion, cleaning, chunking, token estimation, reporting, optional compression
- Test suite and GitHub CI workflow

[0.2.0]: https://github.com/juanlazarde/ContextRefinery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/juanlazarde/ContextRefinery/releases/tag/v0.1.0