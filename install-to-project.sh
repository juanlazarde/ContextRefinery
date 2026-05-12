#!/usr/bin/env bash
# install-to-project.sh — installs doc-preprocessor hooks into a target project
#
# Usage:
#   ./install-to-project.sh                  # installs into current directory
#   ./install-to-project.sh /path/to/project # installs into specified directory
#   ./install-to-project.sh --global         # installs CLI + skill only (no project target)

set -euo pipefail

REPO="juanlazarde/ContextRefinery"
RAW_BASE="https://raw.githubusercontent.com/$REPO/main"
PACKAGE_URL="git+https://github.com/$REPO.git"
SKILL_DEST="$HOME/.claude/skills/doc-preprocess.md"

# Detect whether we're running from a real file (local) or piped via curl (remote)
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SKILL_SRC="$SCRIPT_DIR/SKILL.md"
    REMOTE_MODE=false
else
    REMOTE_MODE=true
fi

# ---------- helpers -----------------------------------------------------------

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# ---------- parse args --------------------------------------------------------

GLOBAL_ONLY=false
TARGET=""

for arg in "$@"; do
    case "$arg" in
        --global) GLOBAL_ONLY=true ;;
        -*) red "Unknown flag: $arg"; exit 2 ;;
        *) TARGET="$arg" ;;
    esac
done

if [[ "$GLOBAL_ONLY" == false ]]; then
    TARGET="${TARGET:-$(pwd)}"
    if [[ ! -d "$TARGET" ]]; then
        red "Target directory does not exist: $TARGET"
        exit 2
    fi
fi

# ---------- step 1: install CLI tools -----------------------------------------

step "Installing CLI tools globally via uv tool"

if [[ "$REMOTE_MODE" == true ]]; then
    PKG_SRC="${PACKAGE_URL}[pdf]"
else
    PKG_SRC="${SCRIPT_DIR}[pdf]"
fi

if command -v uv &>/dev/null; then
    uv tool install --reinstall "$PKG_SRC" && green "Installed with uv tool (pdf support)"
elif command -v pip &>/dev/null; then
    yellow "uv not found — falling back to pip install --user"
    pip install --user "$PKG_SRC" && green "Installed with pip"
else
    red "Neither uv nor pip found. Install uv (https://docs.astral.sh/uv/) and retry."
    exit 1
fi

# Verify entrypoints landed on PATH
if ! command -v doc-preprocess-hook &>/dev/null; then
    yellow "Warning: doc-preprocess-hook not found on PATH after install."
    yellow "You may need to add uv's tool bin to your PATH:"
    yellow "  export PATH=\"\$(uv tool dir)/bin:\$PATH\""
fi

# ---------- step 2: install Claude Code skill ----------------------------------

step "Installing Claude Code skill to ~/.claude/skills/"

mkdir -p "$(dirname "$SKILL_DEST")"
if [[ "$REMOTE_MODE" == true ]]; then
    curl -fsSL "$RAW_BASE/SKILL.md" -o "$SKILL_DEST"
    green "Skill fetched and installed: $SKILL_DEST"
else
    cp "$SKILL_SRC" "$SKILL_DEST"
    green "Skill installed: $SKILL_DEST"
fi

# ---------- step 3: inject project-level agent instructions -------------------

if [[ "$GLOBAL_ONLY" == true ]]; then
    green "\nGlobal install complete. Skill and CLI are ready."
    green "Run without --global (or with a path) to also inject CLAUDE.md / AGENTS.md into a project."
    exit 0
fi

step "Injecting pre-run hook instructions into $TARGET"

CLAUDE_SNIPPET='
## Pre-Run Hook: Document Preprocessing

Before reading or processing any `.md`, `.txt`, or `.pdf` file, run:

```bash
doc-preprocess-hook "{input_path}" --out-dir ".skill_work/preprocessed"
```

For a directory of files:

```bash
doc-preprocess-hook "{input_dir}" --out-dir ".skill_work/preprocessed" --pattern "**/*" --workers 4
```

**Output selection rule:**
1. Use `*.cleaned.md` as the primary input.
2. Load `*.report.json` when citations or source-fidelity checks are needed.
3. Load `*.chunks.json` when retrieval over sections is needed.
4. If preprocessing fails, disclose it — do not silently fall back to raw files.

**Defaults:** no compression, no aggressive cleaning, no auto-install unless explicitly requested.
'

AGENTS_SNIPPET='
## Pre-Run Hook: Document Preprocessing

Before any skill reads or processes user-provided `.md`, `.txt`, or `.pdf` files,
run `doc-preprocess-hook` first. Use the cleaned output as the primary task input.

Single file:

```bash
doc-preprocess-hook "{input_path}" --out-dir "{work_dir}/preprocessed"
```

Folder:

```bash
doc-preprocess-hook "{input_dir}" --out-dir "{work_dir}/preprocessed" --pattern "**/*" --workers 4
```

**Output preference:** `*.cleaned.md` > `*.report.json` (citations) > `*.chunks.json` (retrieval).
**Failure policy:** partial success → continue with successful files and disclose failures.
Total failure → stop and report. Never silently use raw files.
**Defaults:** compress=false, aggressive_clean=false, auto_install_deps=false.
'

# Inject into CLAUDE.md
CLAUDE_MD="$TARGET/CLAUDE.md"
MARKER="## Pre-Run Hook: Document Preprocessing"

if [[ -f "$CLAUDE_MD" ]]; then
    if grep -qF "$MARKER" "$CLAUDE_MD"; then
        yellow "CLAUDE.md already contains the pre-run hook section — skipping."
    else
        printf '%s' "$CLAUDE_SNIPPET" >> "$CLAUDE_MD"
        green "Appended pre-run hook section to $CLAUDE_MD"
    fi
else
    printf '# Claude Instructions\n%s' "$CLAUDE_SNIPPET" > "$CLAUDE_MD"
    green "Created $CLAUDE_MD with pre-run hook section"
fi

# Inject into AGENTS.md
AGENTS_MD="$TARGET/AGENTS.md"

if [[ -f "$AGENTS_MD" ]]; then
    if grep -qF "$MARKER" "$AGENTS_MD"; then
        yellow "AGENTS.md already contains the pre-run hook section — skipping."
    else
        printf '%s' "$AGENTS_SNIPPET" >> "$AGENTS_MD"
        green "Appended pre-run hook section to $AGENTS_MD"
    fi
else
    printf '# Agent Instructions\n%s' "$AGENTS_SNIPPET" > "$AGENTS_MD"
    green "Created $AGENTS_MD with pre-run hook section"
fi

# ---------- step 4: add .skill_work/ to .gitignore ---------------------------

GITIGNORE="$TARGET/.gitignore"
GITIGNORE_ENTRY=".skill_work/"

if [[ -f "$GITIGNORE" ]]; then
    if grep -qF "$GITIGNORE_ENTRY" "$GITIGNORE"; then
        yellow ".gitignore already contains $GITIGNORE_ENTRY — skipping."
    else
        printf '\n%s\n' "$GITIGNORE_ENTRY" >> "$GITIGNORE"
        green "Added $GITIGNORE_ENTRY to $GITIGNORE"
    fi
else
    printf '%s\n' "$GITIGNORE_ENTRY" > "$GITIGNORE"
    green "Created $GITIGNORE with $GITIGNORE_ENTRY"
fi

# ---------- done --------------------------------------------------------------

printf '\n'
green "Done. doc-preprocessor is wired into: $TARGET"
printf '\nNext steps:\n'
printf '  1. Verify CLI is on PATH:  doc-preprocess-hook --help\n'
printf '  2. Verify skill loaded:    check ~/.claude/skills/doc-preprocess.md\n'
