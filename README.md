# doc-preprocessor

Deterministic-first document preprocessing pipeline for LLM input optimization.

## Features
- Ingest `.md`, `.txt`, `.pdf`
- Deterministic cleaning with audit trail
- Heading-aware chunking with safe max-token split behavior
- Approximate token estimation (`ceil(len(text)/4)`)
- Optional LLMLingua compression (per chunk)
- CLI and installable console script

## Install

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e .[pdf]
pip install -e .[compression]
```

## Usage

```bash
python preprocess.py input.pdf --compress --target_tokens 2000
# or

doc-preprocess input.pdf --compress --target_tokens 2000
```

## Output artifacts
For `input.pdf`:
- `input.extracted.md`
- `input.cleaned.md`
- `input.chunks.json`
- `input.report.json`

Use `--dry-run` to avoid writing files.
