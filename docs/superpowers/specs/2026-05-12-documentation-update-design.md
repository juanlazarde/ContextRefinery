# Documentation Update Design — 2026-05-12

## Goal

Keep all user-facing and agent-facing documentation current with the code changes landed since `v0.1.0`.

## Scope

Full sweep (Option C): README, CHANGELOG, doc/PLAN.md, AGENTS.md, CLAUDE.md, SKILL.md, pyproject.toml version bump.

## Files and Changes

### CHANGELOG.md
- Version `[Unreleased]` block as `[0.2.0] - 2026-05-12`.
- No content changes to existing entries.
- Add comparison link footer if GitHub remote is present.

### README.md

1. **Breaking change notice** — new `## Breaking Changes` section noting that single-file output now goes to `<input_parent>/outputs/` (not next to the input), with migration guidance (`--out-dir .` restores old behavior).
2. **`install-to-project.sh` section** — new `## Install into a Project` section after the existing Install section, documenting the three usage modes: default (current dir), explicit path, `--global`.
3. **`--max-file-mb 0` clarification** — add note to the existing `--max-file-mb` entry in Common Flags that `0` rejects all non-empty files.

### doc/PLAN.md

Update affected subsections to reflect current implementation:

- **Batch Processing**: `ordered_results=False` returns completion-arrival order; `files_per_sec` is `inf` when duration rounds to 0ms with ≥1 success.
- **Skills Pre-Run Hook / Stable run IDs**: format is now `<timestamp>_<uuid4_hex8>` (random, not input-hash-based).
- **Ingestion and Dependencies**: `get_installed_version("pymupdf")` imports `fitz`; `importlib.invalidate_caches()` called after successful install.
- **Validation Status**: update test count to current passing count.

### AGENTS.md
- Run ID description: remove "derived from normalized input paths and hook options", replace with "unique per call".
- Add one-liner to defaults noting `--max-file-mb 0` rejects all non-empty files.

### CLAUDE.md
- Same run ID fix as AGENTS.md.
- Add `--max-file-mb 0` note to defaults/flags section.

### SKILL.md
- Same run ID fix.
- Add `--max-file-mb 0` note.

### pyproject.toml
- Bump version from `0.1.0` to `0.2.0`.

## Success Criteria

- All docs accurately reflect current code behavior.
- No references to stale run ID format remain.
- Breaking output-dir change is discoverable in README.
- `install-to-project.sh` is documented.
- Version is consistent across CHANGELOG, pyproject.toml.
