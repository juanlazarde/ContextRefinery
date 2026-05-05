# Claude Instructions: doc_preprocessor Pre-Run Hook

Use this repository the same way `AGENTS.md` instructs Codex-style agents.

Before reading or processing user-provided `.md`, `.txt`, or `.pdf` documents, run the pre-run hook and use the cleaned files as the primary inputs.

## Required Pre-Run Rule

Run `doc-preprocess-hook` on explicitly declared files or directories before document analysis tasks.

Single file:

```bash
doc-preprocess-hook "{input_path}" --out-dir "{work_dir}/preprocessed"
```

Directory:

```bash
doc-preprocess-hook "{input_dir}" --out-dir "{work_dir}/preprocessed" --pattern "**/*" --workers 4
```

Python API:

```python
from pathlib import Path

from doc_preprocessor import SkillPreRunOptions, preprocess_for_skill

result = preprocess_for_skill(
    [Path("input.md")],
    SkillPreRunOptions(out_dir=Path(".skill_work/preprocessed"), workers=4),
)
```

## Use These Outputs

1. Prefer `*.cleaned.md`.
2. Load `*.report.json` when citations, audit details, or source-fidelity checks matter.
3. Load `*.chunks.json` when retrieval over sections matters.
4. If preprocessing fails, disclose the failure. Do not silently continue on raw files.

## Defaults

- No compression unless requested.
- No aggressive cleaning unless requested.
- No dependency auto-install unless requested.
- Do not scan entire repositories unless explicitly asked.

## SKILL.md Compatibility

When packaging this as a Claude Skill, copy the pre-run section from `AGENTS.md` or this file into `SKILL.md`.

