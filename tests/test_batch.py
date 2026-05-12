from pathlib import Path
import json

from doc_preprocessor.main import BatchOptions, FileFailure, PipelineOptions, PipelineResult, cli, run_pipeline_batch
from doc_preprocessor.ingest import PDF_DEP_ERROR, DocumentIngestor


def test_discovery_filter_and_sort(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "b.txt").write_text("b", encoding="utf-8")
    (in_dir / "a.md").write_text("a", encoding="utf-8")
    (in_dir / "x.bin").write_bytes(b"x")

    code = cli(["--input-dir", str(in_dir), "--dry-run"])
    assert code == 0


def test_conflicting_auto_install_flags_invalid(tmp_path: Path, capsys):
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    code = cli([str(f), "--auto-install-deps", "--no-auto-install-deps"])
    out = capsys.readouterr().out
    assert code == 2
    assert "Cannot use --auto-install-deps and --no-auto-install-deps together." in out


def test_batch_default_cleaned_and_report(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "sub").mkdir()
    (in_dir / "sub" / "a.md").write_text("# A\nBody", encoding="utf-8")

    out_dir = tmp_path / "out"
    code = cli(["--input-dir", str(in_dir), "--out-dir", str(out_dir)])
    assert code == 0
    assert (out_dir / "sub" / "a__md.cleaned.md").exists()
    assert (out_dir / "batch_report.json").exists()
    payload = json.loads((out_dir / "batch_report.json").read_text(encoding="utf-8"))
    assert payload["total_files"] == 1
    assert payload["results"][0]["status"] == "success"


def test_batch_all_artifacts(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.md").write_text("# A\nBody", encoding="utf-8")

    out_dir = tmp_path / "out"
    code = cli(["--input-dir", str(in_dir), "--out-dir", str(out_dir), "--all-artifacts"])
    assert code == 0
    assert (out_dir / "a__md.cleaned.md").exists()
    assert (out_dir / "a__md.extracted.md").exists()
    assert (out_dir / "a__md.chunks.json").exists()
    assert (out_dir / "a__md.report.json").exists()
    assert (out_dir / "a__md.diff.md").exists()


def test_batch_partial_failure_exit_code(tmp_path: Path, monkeypatch):
    good = tmp_path / "good.md"
    bad = tmp_path / "bad.pdf"
    good.write_text("# Good\nBody", encoding="utf-8")
    bad.write_bytes(b"%PDF")
    monkeypatch.setattr(DocumentIngestor, "_load_pdf", lambda self, path: (_ for _ in ()).throw(RuntimeError(PDF_DEP_ERROR)))

    code = cli([str(good), str(bad), "--workers", "2"])
    assert code == 1


def test_missing_dependency_default_does_not_install(tmp_path: Path, monkeypatch):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF")
    monkeypatch.setattr(DocumentIngestor, "_load_pdf", lambda self, path: (_ for _ in ()).throw(RuntimeError(PDF_DEP_ERROR)))
    result = run_pipeline_batch(
        [bad],
        PipelineOptions(dry_run=True, all_artifacts=False, auto_install_deps=False),
        BatchOptions(workers=1),
    )
    assert result.failed == 1
    fail = result.results[0]
    assert isinstance(fail, FileFailure)
    assert fail.dependency_events == []


def test_auto_install_dry_run_records_event(tmp_path: Path, monkeypatch):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF")
    monkeypatch.setattr(DocumentIngestor, "_load_pdf", lambda self, path: (_ for _ in ()).throw(RuntimeError(PDF_DEP_ERROR)))
    result = run_pipeline_batch(
        [bad],
        PipelineOptions(dry_run=True, all_artifacts=False, auto_install_deps=True),
        BatchOptions(workers=1),
    )
    assert result.failed == 1
    fail = result.results[0]
    assert isinstance(fail, FileFailure)
    assert fail.dependency_events
    ev = fail.dependency_events[0]
    assert ev["package"] == "markitdown"
    assert ev["package_manager"] == "pip"
    assert "would install" in ev["stdout_tail"]


def test_fail_fast_best_effort_message(tmp_path: Path, capsys, monkeypatch):
    good = tmp_path / "good.md"
    bad = tmp_path / "bad.pdf"
    good.write_text("# Good\nBody", encoding="utf-8")
    bad.write_bytes(b"%PDF")
    monkeypatch.setattr(DocumentIngestor, "_load_pdf", lambda self, path: (_ for _ in ()).throw(RuntimeError(PDF_DEP_ERROR)))

    code = cli([str(good), str(bad), "--fail-fast"])
    out = capsys.readouterr().out
    assert code == 1
    assert "best effort" in out


def test_fail_fast_report_accounting_complete(tmp_path: Path):
    good = tmp_path / "good.md"
    bad = tmp_path / "bad.pdf"
    good.write_text("# Good\nBody", encoding="utf-8")
    bad.write_bytes(b"%PDF")

    result = run_pipeline_batch(
        [good, bad],
        PipelineOptions(dry_run=True, all_artifacts=False),
        BatchOptions(workers=2, continue_on_error=False),
    )
    assert result.total_files == 2
    assert len(result.results) == 2
    assert result.total_files == (result.succeeded + result.failed)


def test_max_file_mb_rejection(tmp_path: Path):
    p = tmp_path / "big.md"
    p.write_text("x" * 5000, encoding="utf-8")
    result = run_pipeline_batch(
        [p],
        PipelineOptions(dry_run=True, all_artifacts=False),
        BatchOptions(workers=1, max_file_mb=0),
    )
    assert result.failed == 1
    assert isinstance(result.results[0], FileFailure)


def test_same_stem_different_extension_no_collision_explicit_batch(tmp_path: Path):
    md = tmp_path / "test.md"
    txt = tmp_path / "test.txt"
    md.write_text("# md", encoding="utf-8")
    txt.write_text("txt", encoding="utf-8")
    out_dir = tmp_path / "out"
    code = cli([str(md), str(txt), "--out-dir", str(out_dir), "--all-artifacts"])
    assert code == 0
    assert (out_dir / "test__md.cleaned.md").exists()
    assert (out_dir / "test__txt.cleaned.md").exists()
    assert (out_dir / "test__md.report.json").exists()
    assert (out_dir / "test__txt.report.json").exists()


def test_same_stem_different_extension_no_collision_input_dir(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "test.md").write_text("# md", encoding="utf-8")
    (in_dir / "test.txt").write_text("txt", encoding="utf-8")
    out_dir = tmp_path / "out"
    code = cli(["--input-dir", str(in_dir), "--out-dir", str(out_dir)])
    assert code == 0
    assert (out_dir / "test__md.cleaned.md").exists()
    assert (out_dir / "test__txt.cleaned.md").exists()


def test_output_stems_deterministic_across_runs(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "test.md").write_text("# md", encoding="utf-8")
    (in_dir / "test.txt").write_text("txt", encoding="utf-8")

    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    code1 = cli(["--input-dir", str(in_dir), "--out-dir", str(out_a), "--all-artifacts"])
    code2 = cli(["--input-dir", str(in_dir), "--out-dir", str(out_b), "--all-artifacts"])
    assert code1 == 0
    assert code2 == 0

    names_a = sorted(p.name for p in out_a.glob("*") if p.name != "batch_report.json")
    names_b = sorted(p.name for p in out_b.glob("*") if p.name != "batch_report.json")
    assert names_a == names_b


def test_ordered_results_false_produces_complete_results(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A\nBody", encoding="utf-8")
    b.write_text("# B\nBody", encoding="utf-8")
    out_dir = tmp_path / "out"

    result = run_pipeline_batch(
        [a, b],
        PipelineOptions(out_dir=out_dir),
        BatchOptions(workers=2, ordered_results=False),
    )
    assert result.total_files == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert len(result.results) == 2


def test_cleaned_batch_content_is_correct(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "doc.md").write_text("# Hello\n\nWorld.\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    code = cli(["--input-dir", str(in_dir), "--out-dir", str(out_dir)])
    assert code == 0
    cleaned = (out_dir / "doc__md.cleaned.md").read_text(encoding="utf-8")
    assert "Hello" in cleaned
    assert "World" in cleaned


def test_ordered_results_true_sorts_results_by_path(tmp_path: Path):
    b = tmp_path / "b.md"
    a = tmp_path / "a.md"
    b.write_text("# B", encoding="utf-8")
    a.write_text("# A", encoding="utf-8")

    result = run_pipeline_batch(
        [b, a],
        PipelineOptions(dry_run=True),
        BatchOptions(workers=1, ordered_results=True),
    )
    paths = [r.input_path for r in result.results if isinstance(r, PipelineResult)]
    assert paths == sorted([a, b], key=str)


def test_ordered_results_false_uses_arrival_order(tmp_path: Path, monkeypatch):
    import time
    from doc_preprocessor import main as main_module

    a = tmp_path / "a.md"  # slow — b should complete first
    b = tmp_path / "b.md"
    a.write_text("# A", encoding="utf-8")
    b.write_text("# B", encoding="utf-8")

    orig = main_module._run_file_task

    def controlled(path, opts, max_mb):
        if path.name == "a.md":
            time.sleep(0.05)
        return orig(path, opts, max_mb)

    monkeypatch.setattr(main_module, "_run_file_task", controlled)

    result = run_pipeline_batch(
        [a, b],
        PipelineOptions(dry_run=True),
        BatchOptions(workers=2, ordered_results=False),
    )
    paths = [r.input_path for r in result.results if isinstance(r, PipelineResult)]
    assert paths == [b, a], f"Expected arrival order [b, a] but got {[p.name for p in paths]}"


def test_files_per_sec_is_inf_when_instantaneous(tmp_path: Path, monkeypatch):
    from doc_preprocessor import main as main_module

    monkeypatch.setattr(main_module, "perf_counter", lambda: 0.0)

    f = tmp_path / "a.md"
    f.write_text("# Hello", encoding="utf-8")

    result = run_pipeline_batch(
        [f],
        PipelineOptions(dry_run=True),
        BatchOptions(workers=1),
    )
    assert result.succeeded == 1
    assert result.files_per_sec == float("inf")
