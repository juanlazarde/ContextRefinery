# doc-preprocessor

Clean up documents before sending them to an LLM — fewer tokens, same structure, full audit trail.

Works on `.md`, `.txt`, and `.pdf` files. Runs on one file or hundreds.

---

## Install

**The fastest way** — run this in your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/juanlazarde/ContextRefinery/main/install-to-project.sh | bash
```

This installs the CLI and wires the pre-run hook into your project's `CLAUDE.md` and `AGENTS.md` so AI agents automatically preprocess documents before reading them.

**Global only** (no project wiring):

```bash
curl -fsSL https://raw.githubusercontent.com/juanlazarde/ContextRefinery/main/install-to-project.sh | bash -s -- --global
```

**From a local clone:**

| What you want | Command |
|---|---|
| Markdown + text only | `pip install -e .` |
| + PDF support | `pip install -e ".[pdf]"` |
| + Compression | `pip install -e ".[pdf,compression]"` |
| Everything | `pip install -e ".[all]"` |

---

## Basic Usage

Process a single file:

```bash
doc-preprocess input.md
```

Output lands in `outputs/input.cleaned.md` by default.

Write all artifacts (diff, chunks, full report):

```bash
doc-preprocess input.md --all-artifacts
```

Process a whole directory:

```bash
doc-preprocess --input-dir ./docs --pattern "**/*" --workers 4
```

---

## What Gets Written

By default, only the cleaned file is written. Pass `--all-artifacts` to get everything:

| File | Contents |
|---|---|
| `*.cleaned.md` | Cleaned text — the one to send to the LLM |
| `*.extracted.md` | Raw extracted text before cleaning |
| `*.chunks.json` | Structure-aware chunks for retrieval |
| `*.report.json` | Metrics, warnings, and audit data |
| `*.diff.md` | Line-by-line diff of extracted vs cleaned |

Batch runs also write a `batch_report.json` summary.

---

## Pre-Run Hook (for AI agents)

When a Claude or Codex skill needs clean inputs, run the hook first:

```bash
# Single file
doc-preprocess-hook notes.md transcript.pdf

# Directory
doc-preprocess-hook ./docs --pattern "**/*"
```

The hook writes cleaned files and a `hook_summary.json`. It skips files it already generated (`.cleaned.md`, `.chunks.json`, etc.) so re-runs are safe.

Use `--require-all-success` if the agent should stop when any input fails to process.

---

## Common Flags

| Flag | What it does |
|---|---|
| `--out-dir PATH` | Where to write output (default: `outputs/` next to the input) |
| `--all-artifacts` | Write every output file, not just the cleaned version |
| `--dry-run` | Process but write nothing |
| `--compress` | Compress output to reduce tokens further |
| `--target-tokens N` | Token budget for compression |
| `--compression-ratio R` | Compression strength hint |
| `--max-chunk-tokens N` | Max tokens per chunk before splitting |
| `--max-file-mb N` | Skip files larger than N MB (`0` rejects all non-empty files) |
| `--aggressive-clean` | Stronger cleanup pass |
| `--fail-fast` | Stop batch processing on first failure |
| `--require-all-success` | Hook exits with failure if any input fails |
| `--auto-install-deps` | Install missing runtime dependencies and retry |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, etc. |

Full flag reference: `doc-preprocess --help`

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All files succeeded |
| `1` | One or more files failed |
| `2` | Bad arguments |

---

## Troubleshooting

**PDF processing fails:**
```bash
pip install markitdown pymupdf
```

**Compression fails:**
```bash
pip install llmlingua
```

---

## Breaking Change in 0.2.0

Output files moved from next to the input to an `outputs/` subdirectory.

```
# Before 0.2.0
input.md → input.cleaned.md

# From 0.2.0
input.md → outputs/input.cleaned.md
```

To get the old behavior: `doc-preprocess input.md --out-dir .`
