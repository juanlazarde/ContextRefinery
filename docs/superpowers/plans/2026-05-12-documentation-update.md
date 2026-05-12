# Documentation Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep all user-facing and agent-facing documentation current with the code changes landed since v0.1.0.

**Architecture:** Direct edits to seven files: CHANGELOG.md (version bump), pyproject.toml (version bump), README.md (three additions), doc/PLAN.md (four stale descriptions), and AGENTS.md / CLAUDE.md / SKILL.md (one stale description + one missing note each). No code changes.

**Tech Stack:** Markdown, TOML, bash (grep for verification).

---

## File Map

| File | Change |
|------|--------|
| `CHANGELOG.md` | `[Unreleased]` → `[0.2.0] - 2026-05-12`; add comparison links |
| `pyproject.toml` | `version = "0.1.0"` → `version = "0.2.0"` |
| `README.md` | Add `## Breaking Changes`, `## Install into a Project`, update `--max-file-mb` entry |
| `doc/PLAN.md` | Fix run ID format, batch ordering, `files_per_sec`, deps; update test count |
| `AGENTS.md` | Add `--max-file-mb 0` note to Recommended Defaults |
| `CLAUDE.md` | Add `--max-file-mb 0` note to Defaults |
| `SKILL.md` | Add `--max-file-mb 0` note near defaults |

---

### Task 1: Version the CHANGELOG and bump pyproject.toml

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml:7`

- [ ] **Step 1: Update CHANGELOG.md**

Replace the `## [Unreleased]` header with the versioned header and add comparison links at the bottom:

In `CHANGELOG.md`, change:
```markdown
## [Unreleased]
```
to:
```markdown
## [0.2.0] - 2026-05-12
```

Then append these lines at the very end of the file:
```markdown

[0.2.0]: https://github.com/juanlazarde/ContextRefinery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/juanlazarde/ContextRefinery/releases/tag/v0.1.0
```

- [ ] **Step 2: Verify CHANGELOG**

Run: `grep "0.2.0\|0.1.0" CHANGELOG.md`

Expected output includes both version headers and the two comparison links at the bottom.

- [ ] **Step 3: Bump version in pyproject.toml**

In `pyproject.toml` line 7, change:
```toml
version = "0.1.0"
```
to:
```toml
version = "0.2.0"
```

- [ ] **Step 4: Verify pyproject.toml**

Run: `grep "^version" pyproject.toml`

Expected: `version = "0.2.0"`

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml
git commit -m "chore: release v0.2.0"
```

---

### Task 2: Add breaking change notice to README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Locate the Install section**

Run: `grep -n "^## " README.md`

Note the line number of `## Install` — insert the new section just before it.

- [ ] **Step 2: Add the Breaking Changes section**

Insert the following block immediately before `## Install`:

```markdown
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

```

- [ ] **Step 3: Verify**

Run: `grep -n "Breaking Changes\|out-dir \." README.md`

Expected: both strings appear.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document breaking output-dir change in README"
```

---

### Task 3: Add install-to-project.sh section to README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find insertion point**

Run: `grep -n "^## " README.md`

Insert the new section after `## Install` (and after the new `## Breaking Changes` section added in Task 2), before `## Quick Start`.

- [ ] **Step 2: Add the section**

Insert the following block immediately before `## Quick Start`:

```markdown
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

```

- [ ] **Step 3: Verify**

Run: `grep -n "Install into a Project\|install-to-project\|--global" README.md`

Expected: all three strings appear.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document install-to-project.sh in README"
```

---

### Task 4: Clarify --max-file-mb 0 in README.md Common Flags

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the existing flag entry**

Run: `grep -n "max-file-mb" README.md`

- [ ] **Step 2: Update the entry**

In `README.md`, change the existing line:
```markdown
- `--max-file-mb N`: skip files larger than N MB in batch mode
```
to:
```markdown
- `--max-file-mb N`: skip files larger than N MB in batch mode (`0` rejects all non-empty files)
```

- [ ] **Step 3: Verify**

Run: `grep "max-file-mb" README.md`

Expected: the line now includes `0` rejects all non-empty files`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: clarify --max-file-mb 0 behavior in README"
```

---

### Task 5: Update doc/PLAN.md — run ID format

**Files:**
- Modify: `doc/PLAN.md`

- [ ] **Step 1: Find the stale lines**

Run: `grep -n "hash8\|normalized input paths\|hash is derived" doc/PLAN.md`

Expected: lines 203–204 (approximately).

- [ ] **Step 2: Replace the stale description**

In `doc/PLAN.md`, change:
```markdown
Stable run IDs:
- format: `<timestamp>_<hash8>`
- hash is derived from normalized input paths and hook options
```
to:
```markdown
Stable run IDs:
- format: `<timestamp>_<uuid4_hex8>`
- unique per call (random UUID suffix — not derived from inputs)
```

- [ ] **Step 3: Verify**

Run: `grep -n "uuid4\|normalized input" doc/PLAN.md`

Expected: `uuid4` appears, `normalized input` does not.

- [ ] **Step 4: Commit**

```bash
git add doc/PLAN.md
git commit -m "docs: update run ID format in PLAN.md"
```

---

### Task 6: Update doc/PLAN.md — batch ordering and files_per_sec

**Files:**
- Modify: `doc/PLAN.md`

- [ ] **Step 1: Find the batch processing section**

Run: `grep -n "ordered_results\|files_per_sec\|completion" doc/PLAN.md`

- [ ] **Step 2: Add ordering behavior after the Batch report bullet**

In `doc/PLAN.md`, find the line:
```markdown
- `batch_report.json` with totals, duration, throughput, failures, and per-file result rows
```

Add the following two lines immediately after it:
```markdown

Result ordering:
- `ordered_results=True` (default): results returned in input-path sort order
- `ordered_results=False`: results returned in completion-arrival order
- `files_per_sec` is `inf` when batch duration rounds to 0ms with ≥1 success; `0.0` when nothing succeeded
```

- [ ] **Step 3: Verify**

Run: `grep -n "completion-arrival\|files_per_sec.*inf" doc/PLAN.md`

Expected: both lines appear.

- [ ] **Step 4: Commit**

```bash
git add doc/PLAN.md
git commit -m "docs: document batch ordering and files_per_sec behavior in PLAN.md"
```

---

### Task 7: Update doc/PLAN.md — dependency fixes and test count

**Files:**
- Modify: `doc/PLAN.md`

- [ ] **Step 1: Fix the get_installed_version note**

In `doc/PLAN.md`, find the Runtime install execution section and add after `- dry-run never installs; records "would install" event`:
```markdown
- `get_installed_version("pymupdf")` imports `fitz` (the PyMuPDF module name)
- `importlib.invalidate_caches()` is called after a successful install so the package is importable in the same process
```

- [ ] **Step 2: Update test count**

In `doc/PLAN.md`, change:
```markdown
- Current status: `46 passed`.
```
to:
```markdown
- Current status: `55 passed`.
```

- [ ] **Step 3: Verify**

Run: `grep -n "55 passed\|invalidate_caches\|fitz.*PyMuPDF" doc/PLAN.md`

Expected: all three lines appear.

- [ ] **Step 4: Commit**

```bash
git add doc/PLAN.md
git commit -m "docs: update deps behavior and test count in PLAN.md"
```

---

### Task 8: Update AGENTS.md — add --max-file-mb 0 note

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Find the Recommended Defaults section**

Run: `grep -n "max_file_mb\|Recommended Defaults" AGENTS.md`

- [ ] **Step 2: Add the note**

In `AGENTS.md`, change:
```markdown
- `max_file_mb: 100`
```
to:
```markdown
- `max_file_mb: 100` (use `0` to reject all non-empty files)
```

- [ ] **Step 3: Verify**

Run: `grep "max_file_mb" AGENTS.md`

Expected: line includes `0` to reject all non-empty files`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: clarify max_file_mb=0 behavior in AGENTS.md"
```

---

### Task 9: Update CLAUDE.md — add --max-file-mb 0 note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Find the Defaults section**

Run: `grep -n "^## Defaults\|max.file.mb\|max_file" CLAUDE.md`

- [ ] **Step 2: Add the note**

The `CLAUDE.md` Defaults section lists items like "No compression unless requested." Add a new bullet:

```markdown
- `--max-file-mb` defaults to `100` MB; use `0` to reject all non-empty files.
```

Add it to the end of the `## Defaults` bullet list.

- [ ] **Step 3: Verify**

Run: `grep "max-file-mb\|max_file" CLAUDE.md`

Expected: the new line appears.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add max-file-mb default note to CLAUDE.md"
```

---

### Task 10: Update SKILL.md — add --max-file-mb 0 note

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Find the relevant location**

Run: `grep -n "max_file_mb\|max-file-mb\|Do not" SKILL.md`

- [ ] **Step 2: Add the note near the Python API max_file_mb line**

In `SKILL.md`, the Python API block contains `max_file_mb=100,`. Add a comment on the same line:

Change:
```python
        max_file_mb=100,
```
to:
```python
        max_file_mb=100,  # use 0 to reject all non-empty files
```

- [ ] **Step 3: Verify**

Run: `grep "max_file_mb" SKILL.md`

Expected: line includes the `# use 0` comment.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "docs: clarify max_file_mb=0 behavior in SKILL.md"
```

---

## Self-Review

**Spec coverage check:**
- [x] CHANGELOG versioned → Task 1
- [x] pyproject.toml bumped → Task 1
- [x] README breaking change → Task 2
- [x] README install-to-project.sh → Task 3
- [x] README --max-file-mb 0 → Task 4
- [x] PLAN.md run ID format → Task 5
- [x] PLAN.md batch ordering + files_per_sec → Task 6
- [x] PLAN.md deps (get_installed_version, invalidate_caches) → Task 7
- [x] PLAN.md test count → Task 7
- [x] AGENTS.md max-file-mb note → Task 8
- [x] CLAUDE.md max-file-mb note → Task 9
- [x] SKILL.md max-file-mb note → Task 10

**Placeholder scan:** None found. All steps have exact content, exact grep commands, and exact expected output.

**Consistency check:** No shared types or method names across tasks — each task edits independent files.
