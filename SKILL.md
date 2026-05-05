# doc-preprocessor Claude Code Skill

Copy this file to `~/.claude/skills/doc-preprocess.md` to register it as a Claude Code skill.

This skill uses the same pre-run contract as `AGENTS.md` for Codex agents and `CLAUDE.md` for Claude Code. Keep those files aligned when changing hook behavior.

---

This skill runs `doc-preprocess-hook` on one or more files or a directory before the main task executes, so cleaned documents reach Claude instead of raw originals.

## When to use

Call this skill (or trigger it as a pre-run step) whenever the task involves:
- Summarizing, extracting, or analyzing a `.md`, `.txt`, or `.pdf` file
- Sending a document to Claude for any purpose

Do not run it on images, audio, spreadsheets, slides, `.docx`, or already-cleaned files ending in `.cleaned.md`.

## Install

```bash
pip install -e ".[pdf]"          # base + PDF support
pip install -e ".[pdf,compression]"  # base + PDF + optional compression
```

After install, both entrypoints should be available:

```bash
doc-preprocess --help
doc-preprocess-hook --help
```

## Invocation patterns

### Single file (most common)

```bash
doc-preprocess-hook "{file_path}" --out-dir "{work_dir}/preprocessed"
```

Read the cleaned file:

```bash
cat "{work_dir}/preprocessed/{stem}__md.cleaned.md"
```

### Folder

```bash
doc-preprocess-hook "{input_dir}" \
  --out-dir "{work_dir}/preprocessed" \
  --pattern "**/*" \
  --workers 4
```

Read `hook_summary.json` to find all cleaned paths:

```bash
cat "{work_dir}/preprocessed/hook_summary.json"
```

### With compression (opt-in only when explicitly requested)

```bash
doc-preprocess-hook "{file_path}" \
  --compress \
  --compression-ratio 0.5 \
  --out-dir "{work_dir}/preprocessed"
```

### Full audit artifacts

```bash
doc-preprocess-hook "{file_path}" \
  --all-artifacts \
  --out-dir "{work_dir}/preprocessed"
```

## Output selection rule

1. Use `*.cleaned.md` as the primary input to the task.
2. If source fidelity or citations are needed, also load `*.report.json`.
3. If the task involves retrieval over sections, also load `*.chunks.json`.
4. If preprocessing failed, fall back to the original file with an explicit warning.
5. Never silently ignore preprocessing failures.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All inputs processed successfully |
| 1 | One or more inputs failed |
| 2 | Invalid CLI arguments |

## Failure policy

- Partial success (some files ok, some failed): continue with the successful cleaned files; disclose failures in the final answer.
- Total failure: stop and report. Do not silently use raw files.
- Missing PDF deps: suggest `pip install markitdown pymupdf` or rerun with
  `--auto-install-deps`.

## Python API (for skill scripts)

```python
from pathlib import Path
from doc_preprocessor import SkillPreRunOptions, preprocess_for_skill

result = preprocess_for_skill(
    [Path("notes.md"), Path("transcript.pdf")],
    SkillPreRunOptions(
        out_dir=Path(".skill_work/preprocessed"),
        workers=4,
        max_file_mb=100,
        require_all_success=False,
    ),
)

if not result.ok:
    raise RuntimeError(f"Preprocessing failed: {result.failures}")

# cleaned_paths is a list[Path] of *.cleaned.md files
for p in result.cleaned_paths:
    text = p.read_text()
    # ... send text to Claude
```

## Do not

- Do not scan entire repos unless the user explicitly asks.
- Do not use raw files when cleaned files succeeded.
- Do not enable compression, aggressive cleaning, or auto-install unless the user
  explicitly requests them.
- Do not hide preprocessing failures.
