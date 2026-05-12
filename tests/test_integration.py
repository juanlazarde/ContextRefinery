from pathlib import Path
import json

from doc_preprocessor.main import PipelineOptions, run_pipeline


def test_end_to_end_default_writes_all_single_file_artifacts(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text\n\nBody text\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    opts = PipelineOptions(out_dir=out_dir)
    result = run_pipeline(input_path, opts)

    assert result.report.cleaned_tokens <= result.report.extracted_tokens
    assert len(result.chunks) >= 1
    assert result.report.chunks >= 1
    assert len(result.written_files) == 1
    assert (out_dir / "input.cleaned.md").exists()
    assert not (out_dir / "input.extracted.md").exists()
    assert not (out_dir / "input.chunks.json").exists()
    assert not (out_dir / "input.report.json").exists()
    assert not (out_dir / "input.diff.md").exists()


def test_disable_all_artifacts_writes_only_cleaned(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text\n\nBody text\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    opts = PipelineOptions(out_dir=out_dir, all_artifacts=False)
    result = run_pipeline(input_path, opts)

    assert len(result.written_files) == 1
    assert (out_dir / "input.cleaned.md").exists()
    assert not (out_dir / "input.extracted.md").exists()


def test_enable_all_artifacts_writes_full_set_with_diff(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text\n\nBody text\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    opts = PipelineOptions(out_dir=out_dir, all_artifacts=True)
    result = run_pipeline(input_path, opts)
    assert len(result.written_files) == 5
    assert (out_dir / "input.extracted.md").exists()
    assert (out_dir / "input.cleaned.md").exists()
    assert (out_dir / "input.chunks.json").exists()
    assert (out_dir / "input.report.json").exists()
    assert (out_dir / "input.diff.md").exists()
    payload = json.loads((out_dir / "input.report.json").read_text(encoding="utf-8"))
    assert "processing_log" in payload
    assert "timings_ms" in payload


def test_default_output_dir_is_outputs_folder(tmp_path: Path):
    input_path = tmp_path / "input.txt"
    input_path.write_text("hello", encoding="utf-8")
    result = run_pipeline(input_path, PipelineOptions())
    expected = tmp_path / "outputs" / "input.cleaned.md"
    assert expected.exists()
    assert expected in result.written_files


def test_dry_run_writes_nothing(tmp_path: Path):
    input_path = tmp_path / "input.txt"
    input_path.write_text("hello", encoding="utf-8")
    opts = PipelineOptions(dry_run=True, out_dir=tmp_path / "out")
    result = run_pipeline(input_path, opts)
    assert result.written_files == []


def test_cleaned_content_is_correct(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text.\n\nBody text.\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    run_pipeline(input_path, PipelineOptions(out_dir=out_dir))
    cleaned = (out_dir / "input.cleaned.md").read_text(encoding="utf-8")
    assert "Title" in cleaned
    assert "Body text" in cleaned


def test_aggressive_clean_option(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text.\n\nBody text.\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = run_pipeline(input_path, PipelineOptions(out_dir=out_dir, aggressive_clean=True))
    assert (out_dir / "input.cleaned.md").exists()
    assert result.report.cleaned_tokens <= result.report.extracted_tokens


def test_unsupported_extension_raises(tmp_path: Path):
    import pytest
    from doc_preprocessor.ingest import DocumentIngestor
    input_path = tmp_path / "file.docx"
    input_path.write_bytes(b"dummy")
    ingestor = DocumentIngestor()
    with pytest.raises(ValueError, match="Unsupported file type"):
        ingestor.load(input_path)


def test_print_single_summary_handles_none_cleaning_reduction(tmp_path: Path, capsys):
    from doc_preprocessor.main import _print_single_summary

    input_path = tmp_path / "input.md"
    input_path.write_text("hello world", encoding="utf-8")
    result = run_pipeline(input_path, PipelineOptions(out_dir=tmp_path / "out"))
    result.report.cleaning_reduction_percent = None

    _print_single_summary(result, dry_run=False)

    out = capsys.readouterr().out
    assert "Cleaning reduction" in out


def test_timing_report_keys_present(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody.\n", encoding="utf-8")
    result = run_pipeline(input_path, PipelineOptions(out_dir=tmp_path / "out", all_artifacts=True))
    timings = result.report.timings_ms
    for key in ("ingest", "clean", "chunk", "compress", "output", "total"):
        assert key in timings
        assert timings[key] >= 0
