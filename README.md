# doc-preprocessor

## Overview

`doc-preprocessor` prepares documents before you send them to an LLM.

It is designed to:

- reduce token usage,
- keep structure (headings, sections, tables),
- keep an audit trail of what changed,
- run on one file or many files.

Supported input formats:

- `.md`
- `.txt`
- `.pdf`

## Breaking Changes

### 0.2.0

**Default single-file output directory changed.**
Output files now go to `<input_parent>/outputs/` instead of next to the input file.

```bash
# Before 0.2.0 — output appeared next to the input:
# input.md → input.cleaned.md

# From 0.2.0 — output goes to outputs/:
# input.md → outputs/input.cleaned.md

# To restore the old behavior:
doc-preprocess input.md --out-dir .
```

## Install

### One-liner (curl)

```bash
curl -fsSL https://raw.githubusercontent.com/juanlazarde/ContextRefinery/main/install-to-project.sh | bash
```

This installs the CLI tools globally (via `uv tool`) and wires the pre-run hook into the current directory. For global-only (no project wiring):

```bash
curl -fsSL https://raw.githubusercontent.com/juanlazarde/ContextRefinery/main/install-to-project.sh | bash -s -- --global
```

> **Requires:** the repo is public on GitHub and `uv` or `pip` is on your PATH. `curl` is pre-installed on macOS and most Linux distros.

### From a local clone

Base install (markdown and text processing only):

```bash
pip install -e .
```

With PDF support:

```bash
pip install -e ".[pdf]"
```

With optional compression:

```bash
pip install -e ".[pdf,compression]"
```

Everything:

```bash
pip install -e ".[all]"
```

## Install into a Project

`install-to-project.sh` wires `doc-preprocessor` into another project by installing
the CLI, registering the Claude Code skill, and injecting the pre-run hook instructions
into that project's `CLAUDE.md` and `AGENTS.md`.

Install into the current directory:

```bash
./install-to-project.sh
```

Install into a specific project:

```bash
./install-to-project.sh /path/to/your/project
```

Install CLI and skill globally without touching any project:

```bash
./install-to-project.sh --global
```

The script also appends `.skill_work/` to the target project's `.gitignore` (idempotent).

## Quick Start

Process one file:

```bash
doc-preprocess input.md
```

Default output:

- `input.cleaned.md`

Write all artifacts:

```bash
doc-preprocess input.md --all-artifacts
```

## Output Files

When `--all-artifacts` is enabled, the tool writes:

- `input.extracted.md` (raw extracted text)
- `input.cleaned.md` (deterministically cleaned text)
- `input.chunks.json` (structure-aware chunks)
- `input.report.json` (metrics, logs, warnings, audit data)
- `input.diff.md` (line-by-line diff: extracted vs cleaned)

## Batch Processing

Process a directory:

```bash
doc-preprocess --input-dir ./docs --pattern "**/*" --workers 4
```

Process explicit files:

```bash
doc-preprocess a.md b.txt c.pdf --workers 4
```

Batch report:

- `batch_report.json`

## Skills Pre-Run Hook

Use the hook when a Codex or Claude skill needs cleaned document inputs before it runs.

Process declared files:

```bash
doc-preprocess-hook notes.md transcript.pdf
```

Process a directory:

```bash
doc-preprocess-hook ./docs --pattern "**/*"
```

Default hook output:

- cleaned files
- `hook_summary.json`

The hook skips generated files such as `*.cleaned.md`, `*.chunks.json`, `*.report.json`, `*.extracted.md`, `*.diff.md`, and anything inside `.doc_preprocessor/`.

Use `--require-all-success` when a skill should stop if any declared input fails.

## Common Flags

- `--all-artifacts`: write full artifact set
- `--dry-run`: run processing but write no files
- `--out-dir PATH`: set output directory
- `--compress`: enable per-chunk compression
- `--target-tokens N`: target token budget for compression
- `--compression-ratio R`: compression ratio hint
- `--max-chunk-tokens N`: max tokens per chunk before safe splitting
- `--fail-fast`: best-effort early stop in batch mode
- `--require-all-success`: hook mode returns failure if any declared input fails
- `--max-file-mb N`: skip files larger than N MB in batch mode (`0` rejects all non-empty files)
- `--aggressive-clean`: stronger deterministic cleanup
- `--log-level LEVEL`: logging level (`DEBUG`, `INFO`, `WARNING`, ...)

Dependency flags:

- `--auto-install-deps`: opt in to allowlisted runtime dependency install + retry
- `--no-auto-install-deps`: hard-disable runtime dependency install

If both dependency flags are passed, CLI exits with code `2`.

## Exit Codes

- `0`: all files succeeded
- `1`: one or more files failed
- `2`: invalid CLI input/config

## Troubleshooting

If PDF processing fails, install (or reinstall) dependencies:

```bash
pip install markitdown pymupdf
```

If compression fails, install:

```bash
pip install llmlingua
```

For full flag help:

```bash
doc-preprocess --help
```
