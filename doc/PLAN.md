# Final Revised Plan: `doc_preprocessor`

## Summary
Build an installable Python package for deterministic-first document preprocessing before LLM usage, with optional LLMLingua compression, strong auditability, and a single CLI for `.md`, `.txt`, and `.pdf`.

## Package Structure
- `doc_preprocessor/__init__.py`
- `doc_preprocessor/ingest.py`
- `doc_preprocessor/clean.py`
- `doc_preprocessor/chunk.py`
- `doc_preprocessor/estimate.py`
- `doc_preprocessor/compress.py`
- `doc_preprocessor/report.py`
- `doc_preprocessor/main.py`
- `preprocess.py`
- `pyproject.toml`
- `README.md`
- `tests/`

## Public API
Expose from `doc_preprocessor/__init__.py`:
- `run_pipeline`
- `PipelineOptions`
- `PipelineResult`

### `PipelineOptions`
- `compress: bool`
- `target_tokens: int | None`
- `compression_ratio: float | None`
- `max_chunk_tokens: int | None`
- `dry_run: bool`
- `out_dir: Path | None`
- `log_level: str`
- `aggressive_clean: bool`

### `PipelineResult`
- `ingest_result`
- `clean_result`
- `chunks`
- `report`
- `written_files`

## Ingestion
Implement `DocumentIngestor.load(path: Path) -> IngestResult`.

Supported inputs:
- `.md`, `.txt`: direct read
- `.pdf`: internal conversion with fallback order:
  1. MarkItDown (defensive import handling)
  2. PyMuPDF (`fitz`)
  3. If neither available, raise:

`PDF support requires MarkItDown or PyMuPDF. Install with: pip install markitdown pymupdf`

No OCR in v1.

Track extraction metadata:
- `source_format`
- `extraction_backend`
- `warnings`
- `extracted_chars`
- `extracted_non_whitespace_chars`
- `extracted_pages` (if available)
- `extraction_warnings`

If extracted text is very small, warn:
- `PDF may be scanned/image-based. OCR not enabled.`

## Deterministic Cleaning
Implement `DocumentCleaner.clean(text) -> CleanResult`.

Rules:
- Normalize whitespace and line endings
- Remove page numbers (regex-based)
- Remove repeated headers/footers conservatively (default)
- Remove duplicate paragraphs (hash-based, preserve order)
- Remove empty/noise lines
- Preserve headings/tables/numbers/names/structure

Modes:
- Default conservative mode
- Optional `--aggressive-clean`

## Loss Audit
`CleanResult.removed` includes:
- `page_numbers_count`
- `duplicate_paragraphs_count`
- `repeated_headers`
- `repeated_footers`
- `removed_lines_sample`
- `duplicate_paragraph_samples`
- `warnings`

## Chunking
Implement `MarkdownChunker.chunk(text) -> list[Chunk]`.

Rules:
- Detect `#`, `##`, `###`
- One chunk per section
- Pre-heading content becomes `Preamble`
- Chunk fields: `id`, `heading`, `text`, `estimated_tokens`

Optional size control:
- `--max-chunk-tokens`
- Split only at paragraph/table boundaries
- Never split mid-table or mid-sentence
- If a single block exceeds max, keep intact and warn:

`Chunk exceeds max because a single block could not be safely split.`

## Token Estimation
Implement `TokenEstimator.estimate(text: str) -> int`:
- `ceil(len(text)/4)`

Track:
- `extracted_tokens`
- `cleaned_tokens`
- `compressed_tokens` (if used)

## Optional Compression
Implement `LLMCompressor`.

Behavior:
- Active only with `--compress`
- Compress per chunk
- Options: `--target_tokens`, `--compression_ratio`
- No auto-install
- If missing dependency, raise:

`LLMLingua not installed. Run: pip install llmlingua`

Compression metrics:
- `pre_compression_tokens`
- `post_compression_tokens`
- `compression_ratio_actual`

## Output Artifacts
For `input.pdf`, write:
- `input.extracted.md`
- `input.cleaned.md`
- `input.chunks.json`
- `input.report.json`

Report includes:
- Source/extraction metadata
- Extraction quality metrics
- Token metrics
- Reduction percentages:
  - `cleaning_reduction_percent`
  - `total_reduction_percent` (if compression enabled)
- Chunk count
- Full removal audit

## CLI
Commands:
- `python preprocess.py input.pdf --compress --target_tokens 2000`
- `doc-preprocess input.pdf --compress --target_tokens 2000`

Flags:
- `--compress`
- `--target_tokens`
- `--compression_ratio`
- `--max-chunk-tokens`
- `--dry-run`
- `--log-level`
- `--out-dir`
- `--aggressive-clean`

Behavior:
- `--dry-run` writes nothing
- Always print token savings summary

## Packaging
`pyproject.toml` includes:
- optional deps:
  - `compression = ["llmlingua"]`
  - `pdf = ["markitdown", "pymupdf"]`
- console script:
  - `doc-preprocess = "doc_preprocessor.main:cli"`

## Test Plan
Unit tests:
- cleaning normalization/page-number removal/header-footer/dedup/audit
- chunk heading parsing/preamble/safe splitting/oversize warning
- token estimator correctness

PDF ingestion tests:
- MarkItDown path
- `fitz` fallback path
- both missing exact error

Integration tests:
- end-to-end `.md/.txt/.pdf`
- output/report validation
- `--dry-run` no writes

Compression tests:
- missing dependency exact failure
- enabled path metrics validation
