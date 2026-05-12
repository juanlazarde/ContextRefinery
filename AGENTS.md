# Agent Instructions: doc_preprocessor Pre-Run Hook

These instructions are the Codex-facing version of the same pre-run contract documented in `CLAUDE.md` and `SKILL.md`. Keep the three files aligned so Codex agents, Claude Code, and packaged Claude Skills run the same preprocessing workflow.

## Goal

Before any skill reads or processes user-provided documents, run `doc_preprocessor` first. Use the cleaned output as the primary input to the skill so token load is reduced while document structure and audit data are preserved.

Claude compatibility:

- Claude Code can read the same contract from `CLAUDE.md`.
- Packaged Claude Skills can read the same contract from `SKILL.md`.
- Copy this pre-run section into `SKILL.md` when packaging this as a Claude Skill.

## Core Behavior

- Single declared file: run the hook on that file.
- Folder or multiple declared files: run the hook in batch mode.
- Use deterministic cleaning by default.
- Do not use compression unless the user or skill explicitly enables it.
- Use cleaned output as the primary skill input.
- Use chunks and reports only when the task needs retrieval, audit data, or source-fidelity checks.

## Recommended Defaults

- `compress: false`
- `aggressive_clean: false`
- `auto_install_deps: false`
- `max_file_mb: 100` (use `0` to reject all non-empty files)
- `workers: 4`
- `all_artifacts: false`
- `require_all_success: false`

## Default Commands

Single file:

```bash
doc-preprocess-hook "{input_path}" --out-dir "{work_dir}/preprocessed"
```

Folder:

```bash
doc-preprocess-hook "{input_dir}" --out-dir "{work_dir}/preprocessed" --pattern "**/*" --workers 4
```

Optional compression:

```bash
doc-preprocess-hook "{input_path}" --compress --compression-ratio 0.5 --out-dir "{work_dir}/preprocessed"
```

Full audit artifacts:

```bash
doc-preprocess-hook "{input_path}" --all-artifacts --out-dir "{work_dir}/preprocessed"
```

## Hook Contract

Input:

- `file_paths: list[str]`
- `input_dir: str | None`
- `skill_name: str`
- `task_goal: str`
- `allow_compression: bool`
- `allow_aggressive_clean: bool`
- `allow_auto_install_deps: bool`

Output:

- `cleaned_files: list[str]`
- `extracted_files: list[str]`
- `chunk_files: list[str]`
- `report_files: list[str]`
- `batch_report: str | None`
- `warnings: list[str]`
- `failures: list[dict]`

The implemented Python API returns `SkillPreRunResult`, with cleaned paths, failures, artifact root, summary path, and success state.

## Skill Input Selection Rule

1. Prefer `*.cleaned.md`.
2. If the task requires citations or source-fidelity checks, also load `*.report.json`.
3. If the task requires retrieval over sections, also load `*.chunks.json`.
4. If cleaning failed, use the original file only with an explicit warning.
5. Never silently ignore preprocessing failures.

## Pre-Run Decision Logic

- `.md`, `.txt`, `.pdf` file: preprocess.
- Folder: batch preprocess with the provided pattern.
- Images, audio, and video: skip unless a future extractor exists.
- Spreadsheets, slides, and `.docx`: skip unless future support is added or a supported extractor is explicitly introduced.
- Already cleaned files ending in `.cleaned.md`: skip to avoid double preprocessing.
- Generated files ending in `.chunks.json`, `.report.json`, `.extracted.md`, or `.diff.md`: skip.
- Files inside `.doc_preprocessor/`: skip.

## Batch Output Rule

For batch skills:

- Use `hook_summary.json` first.
- Use `batch_report.json` only when full batch artifacts are needed.
- Pass only successful cleaned files to the skill.
- Mention failed files in the final answer when they affect the result.

## Failure Policy

- If all preprocessing fails, stop and report the failure.
- If some files succeed, continue with successful cleaned files and disclose failures.
- If a dependency is missing and auto-install is disabled, show install guidance.
- If auto-install is enabled, retry once.

## Do Not

- Do not scan entire repos unless the user explicitly asks.
- Do not use raw files when cleaned files succeeded.
- Do not enable compression, aggressive cleaning, or auto-install unless requested.
- Do not hide preprocessing failures.

## Skill Config Block Example

```yaml
pre_run:
    enabled: true
    tool: doc_preprocessor
    mode: auto
    input_types:
        - .md
        - .txt
        - .pdf
    output_preference:
        primary: cleaned_md
        secondary:
            - chunks_json
            - report_json
    defaults:
        compress: false
        aggressive_clean: false
        auto_install_deps: false
        max_file_mb: 100
        workers: 4
        all_artifacts: false
    failure_policy:
        partial_success: continue
        total_failure: stop
        disclose_failures: true
```

## Python Hook Wrapper

```python
from pathlib import Path

from doc_preprocessor import SkillPreRunOptions, preprocess_for_skill


def preprocess_documents_for_skill(
    file_paths=None,
    input_dir=None,
    work_dir=".skill_work",
    compress=False,
    aggressive_clean=False,
    auto_install_deps=False,
):
    inputs = [Path(p) for p in (file_paths or [])]
    if input_dir:
        inputs.append(Path(input_dir))

    return preprocess_for_skill(
        inputs,
        SkillPreRunOptions(
            out_dir=Path(work_dir) / "preprocessed",
            compress=compress,
            aggressive_clean=aggressive_clean,
            auto_install_deps=auto_install_deps,
            workers=4,
            max_file_mb=100,
            require_all_success=False,
        ),
    )
```
