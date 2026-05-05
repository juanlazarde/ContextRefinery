from pathlib import Path
import json

from doc_preprocessor.hooks import (
    SkillPreRunOptions,
    cli,
    preprocess_for_skill,
)


def test_hook_explicit_files_default_cleaned_only(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.txt"
    a.write_text("# A\nBody", encoding="utf-8")
    b.write_text("Body", encoding="utf-8")
    out_dir = tmp_path / "hook"

    result = preprocess_for_skill([a, b], SkillPreRunOptions(out_dir=out_dir))

    assert result.ok
    assert result.succeeded == 2
    assert result.failed == 0
    assert len(result.cleaned_paths) == 2
    assert result.summary_path.exists()
    payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == result.run_id
    assert payload["input_count"] == 2
    assert payload["artifact_root"] == str(out_dir)


def test_hook_directory_and_file_mixed_inputs(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A", encoding="utf-8")
    file_input = tmp_path / "b.txt"
    file_input.write_text("B", encoding="utf-8")

    result = preprocess_for_skill([docs, file_input], SkillPreRunOptions(out_dir=tmp_path / "hook"))

    assert result.ok
    assert result.succeeded == 2
    assert sorted(p.name for p in result.cleaned_paths) == ["a__md.cleaned.md", "b__txt.cleaned.md"]


def test_hook_skip_rules(tmp_path: Path):
    source = tmp_path / "source.md"
    cleaned = tmp_path / "source.cleaned.md"
    report = tmp_path / "source.report.json"
    hidden = tmp_path / ".doc_preprocessor" / "x.md"
    hidden.parent.mkdir()
    source.write_text("# Source", encoding="utf-8")
    cleaned.write_text("cleaned", encoding="utf-8")
    report.write_text("{}", encoding="utf-8")
    hidden.write_text("hidden", encoding="utf-8")

    result = preprocess_for_skill(
        [source, cleaned, report, hidden],
        SkillPreRunOptions(out_dir=tmp_path / "hook"),
    )

    assert result.succeeded == 1
    assert len(result.cleaned_paths) == 1
    payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert len(payload["warnings"]) == 3


def test_hook_require_all_success(tmp_path: Path):
    good = tmp_path / "good.md"
    missing = tmp_path / "missing.md"
    good.write_text("# Good", encoding="utf-8")

    result = preprocess_for_skill(
        [good, missing],
        SkillPreRunOptions(out_dir=tmp_path / "hook", require_all_success=True),
    )

    assert not result.ok
    assert result.succeeded == 1
    assert result.failed == 1


def test_hook_all_artifacts(tmp_path: Path):
    source = tmp_path / "a.md"
    source.write_text("# A\nBody", encoding="utf-8")
    out_dir = tmp_path / "hook"

    result = preprocess_for_skill(
        [source],
        SkillPreRunOptions(out_dir=out_dir, all_artifacts=True),
    )

    assert result.ok
    assert (out_dir / "a__md.cleaned.md").exists()
    assert (out_dir / "a__md.extracted.md").exists()
    assert (out_dir / "a__md.chunks.json").exists()
    assert (out_dir / "a__md.report.json").exists()
    assert (out_dir / "a__md.diff.md").exists()


def test_hook_cli_invalid_no_inputs():
    assert cli([]) == 2


def test_hook_cli_partial_failure_allowed(tmp_path: Path):
    good = tmp_path / "good.md"
    missing = tmp_path / "missing.md"
    good.write_text("# Good", encoding="utf-8")

    assert cli([str(good), str(missing), "--out-dir", str(tmp_path / "hook")]) == 0


def test_hook_cli_require_all_success_failure(tmp_path: Path):
    good = tmp_path / "good.md"
    missing = tmp_path / "missing.md"
    good.write_text("# Good", encoding="utf-8")

    assert cli([
        str(good),
        str(missing),
        "--out-dir",
        str(tmp_path / "hook"),
        "--require-all-success",
    ]) == 1
