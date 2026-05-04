from pathlib import Path

from doc_preprocessor.main import PipelineOptions, run_pipeline


def test_end_to_end_and_outputs(tmp_path: Path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# Title\n\nBody text\n\nBody text\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    opts = PipelineOptions(out_dir=out_dir)
    result = run_pipeline(input_path, opts)

    assert result.report.cleaned_tokens <= result.report.extracted_tokens
    assert len(result.chunks) >= 1
    assert len(result.written_files) == 4
    assert (out_dir / "input.extracted.md").exists()
    assert (out_dir / "input.cleaned.md").exists()
    assert (out_dir / "input.chunks.json").exists()
    assert (out_dir / "input.report.json").exists()


def test_dry_run_writes_nothing(tmp_path: Path):
    input_path = tmp_path / "input.txt"
    input_path.write_text("hello", encoding="utf-8")
    opts = PipelineOptions(dry_run=True, out_dir=tmp_path / "out")
    result = run_pipeline(input_path, opts)
    assert result.written_files == []
