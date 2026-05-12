# Implementation Plan and Current State: `doc_preprocessor`

## Summary
`doc_preprocessor` is implemented as a deterministic-first preprocessing package for LLM input optimization, with:
- single-file and batch processing,
- conservative deterministic cleaning,
- structure-aware chunking,
- optional compression,
- audit/report artifacts,
- production-oriented repo scaffolding (tests, CI, contribution templates).

This document reflects what is actually implemented in the repository right now.

## Package and Runtime Layout
Core Python package:
- `doc_preprocessor/ingest.py`
- `doc_preprocessor/clean.py`
- `doc_preprocessor/chunk.py`
- `doc_preprocessor/estimate.py`
- `doc_preprocessor/compress.py`
- `doc_preprocessor/deps.py`
- `doc_preprocessor/hooks.py`
- `doc_preprocessor/report.py`
- `doc_preprocessor/main.py`
- `doc_preprocessor/__init__.py`

Entry points:
- console script: `doc-preprocess` via `pyproject.toml`
- console script: `doc-preprocess-hook` via `pyproject.toml`

Packaging/test metadata:
- `pyproject.toml`
- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `SKILL.md`
- `tests/`

## Public API
Exported from package root:
- `run_pipeline`
- `run_pipeline_batch`
- `PipelineOptions`
- `PipelineResult`
- `BatchOptions`
- `BatchResult`
- `FileFailure`
- `SkillPreRunOptions`
- `SkillPreRunResult`
- `preprocess_for_skill`

### Data models in use
- `PipelineOptions`
  - `compress`, `target_tokens`, `compression_ratio`, `max_chunk_tokens`
  - `dry_run`, `out_dir`, `log_level`, `aggressive_clean`
  - `all_artifacts`
  - `output_stem`
  - `auto_install_deps`
- `PipelineResult`
  - `input_path`, `ingest_result`, `clean_result`, `chunks`, `report`, `written_files`
- `BatchOptions`
  - `input_dir`, `pattern`, `recursive`, `workers`
  - `continue_on_error`, `ordered_results`, `max_file_mb`
- `BatchResult`
  - `total_files`, `succeeded`, `failed`, `results`, `duration_ms`, `files_per_sec`
- `FileFailure`
  - `path`, `error`, `dependency_events`
- `SkillPreRunOptions`
  - `out_dir`, `all_artifacts`, `compress`, `target_tokens`, `compression_ratio`
  - `max_chunk_tokens`, `workers`, `fail_fast`, `max_file_mb`
  - `require_all_success`, `pattern`, `aggressive_clean`, `auto_install_deps`, `dry_run`
- `SkillPreRunResult`
  - `run_id`, `summary_path`, `cleaned_paths`, `failures`, `succeeded`, `failed`, `artifact_root`, `ok`

## Ingestion and Dependencies
Supported inputs:
- `.md`, `.txt`, `.pdf`

PDF backend order:
1. MarkItDown
2. PyMuPDF (`fitz`)
3. explicit failure message if unavailable

Dependency installation model:
- Primary model is upfront install from `pyproject.toml` (`pip install -e .`).
- Runtime remediation exists as opt-in control:
  - `--auto-install-deps` enables allowlisted self-healing
  - `--no-auto-install-deps` hard-disables it
- conflict handling:
  - passing both flags returns exit code `2` with an explicit error.

Allowlisted runtime remediation mapping:
- `fitz -> pymupdf`
- `pymupdf -> pymupdf`
- `markitdown -> markitdown`
- `llmlingua -> llmlingua`

Runtime install execution:
- `sys.executable -m pip install <package>`
- process-wide lock + shared registry for attempted/success/failed packages
- one retry per affected file
- dry-run never installs; records "would install" event

## Deterministic Processing Pipeline
### Cleaning (`clean.py`)
Implemented deterministic rules:
- normalize whitespace and line endings
- remove page numbers
- conservative repeated header/footer removal
- duplicate paragraph removal (hash-based)
- noise/empty-line handling while preserving structure

Loss audit includes:
- `page_numbers_count`
- `duplicate_paragraphs_count`
- `repeated_headers`
- `repeated_footers`
- `removed_lines_sample`
- `duplicate_paragraph_samples`
- `warnings`

### Chunking (`chunk.py`)
- headings: `#`, `##`, `###`
- pre-heading content mapped to `Preamble`
- safe optional split via `max_chunk_tokens`
- no mid-table split; warning for unsplittable oversized block

### Token Estimation (`estimate.py`)
- `ceil(len(text)/4)`

### Optional Compression (`compress.py`)
- only when `--compress`
- per-chunk compression
- reports compression metrics

## Output Semantics
Default per-file output:
- only `*.cleaned.md`

With `--all-artifacts`:
- `*.extracted.md`
- `*.cleaned.md`
- `*.chunks.json`
- `*.report.json`
- `*.diff.md`

`report.json` includes:
- extraction metadata
- token metrics and reduction percentages
- chunk count
- cleaning loss audit
- `processing_log`
- `timings_ms`
- `dependency_events`

## Batch Processing
Execution model:
- `ThreadPoolExecutor` whole-file parallelism

Input modes:
- `--input-dir` + `--pattern`
- multiple explicit file paths

Fail-fast behavior:
- best-effort (stop scheduling + cancel pending; running tasks may complete)
- report always includes terminal status for every discovered file

Batch report:
- `batch_report.json` with totals, duration, throughput, failures, and per-file result rows

Result ordering:
- `ordered_results=True` (default): results returned in input-path sort order
- `ordered_results=False`: results returned in completion-arrival order
- `files_per_sec` is `inf` when batch duration rounds to 0ms with ≥1 success; `0.0` when nothing succeeded

### Collision-safe batch naming (implemented)
To avoid overwrites when files share stem names:
- batch stem defaults to `<stem>__<ext>` (e.g., `test__md`, `test__pdf`)
- if still colliding, suffix with stable hash: `<stem>__<ext>__<hash8>`
- single-file naming remains unchanged

## Skills Pre-Run Hook
The repository includes a hook layer for Codex and Claude skill workflows:
- API: `preprocess_for_skill(inputs, options)`
- CLI: `doc-preprocess-hook`
- Codex instruction artifact: `AGENTS.md`
- Claude Code instruction artifact: `CLAUDE.md`
- packaged Claude Skill instruction artifact: `SKILL.md`

Hook behavior:
- accepts mixed explicit files and directories
- classifies every input before execution
- directories use pattern-based discovery
- files use the existing single/batch pipeline path
- writes outputs under `.doc_preprocessor/skill_runs/<run_id>/` by default
- writes `hook_summary.json` for skill routing

Skip rules:
- skip `*.cleaned.md`
- skip `*.chunks.json`
- skip `*.report.json`
- skip `*.extracted.md`
- skip `*.diff.md`
- skip `batch_report.json`
- skip anything inside `.doc_preprocessor/`

Stable run IDs:
- format: `<timestamp>_<uuid4_hex8>`
- unique per call (random UUID suffix — not derived from inputs)

Hook summary fields:
- `run_id`
- `input_count`
- `succeeded`
- `failed`
- `cleaned_paths`
- `warnings`
- `failures`
- `artifact_root`
- `options_used`

Failure behavior:
- partial success is allowed by default
- `require_all_success=True` marks the hook result as failed when any input fails

`AGENTS.md`, `CLAUDE.md`, and `SKILL.md` document the same pre-run contract so Codex agents, Claude Code, and packaged Claude Skills can run the hook consistently. They include the default commands, hook contract, input selection rules, failure policy, safety defaults, and Python wrapper examples.

Compatibility rules:
- `AGENTS.md` is the repo-level instruction file for Codex-style agents.
- `CLAUDE.md` is the repo-level instruction file for Claude Code.
- `SKILL.md` is the portable Claude Skill instruction artifact.
- Keep all three aligned when changing hook behavior.
- Copy the pre-run section into `SKILL.md` when packaging this as a Claude Skill.

## CLI Contract
Main flags implemented:
- `--input-dir`, `--pattern`, `--workers`, `--fail-fast`, `--max-file-mb`
- `--compress`, `--target-tokens`, `--compression-ratio`, `--max-chunk-tokens`
- `--dry-run`, `--out-dir`, `--log-level`, `--aggressive-clean`
- `--all-artifacts`
- `--auto-install-deps`, `--no-auto-install-deps`
- hook-specific: `doc-preprocess-hook ... --require-all-success`

Exit codes:
- `0`: success
- `1`: one or more processing failures
- `2`: invalid CLI/config

## Repository Tooling and Governance
Implemented repo support files:
- `AGENTS.md` (agent/skill pre-run hook instructions)
- `CLAUDE.md` (Claude Code pre-run hook instructions)
- `SKILL.md` (portable Claude Skill pre-run hook instructions)
- `.github/workflows/ci.yml` (pytest CI)
- issue templates (`bug_report`, `feature_request`, `config.yml`)
- PR template
- `CODEOWNERS`
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `LICENSE`
- `.gitignore`, `.editorconfig`, `CHANGELOG.md`

## Validation Status
- Test suite is implemented and passing locally.
- Current status: `46 passed`.
