from doc_preprocessor.chunk import MarkdownChunker


def test_heading_parsing_and_preamble():
    text = "Intro line\n\n# H1\nA\n\n## H2\nB"
    chunks = MarkdownChunker().chunk(text)
    assert chunks[0].heading == "Preamble"
    assert chunks[1].heading == "H1"
    assert chunks[2].heading == "H2"


def test_chunk_splitting_respects_boundaries():
    text = "# H\n" + ("Paragraph one sentence.\n\n" * 20)
    chunker = MarkdownChunker(max_chunk_tokens=30)
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    for ch in chunks:
        assert "\n\n" in ch.text or ch.text.startswith("# H")


def test_oversized_single_block_warning():
    long_para = "# H\n" + ("word " * 500)
    chunker = MarkdownChunker(max_chunk_tokens=20)
    chunks = chunker.chunk(long_para)
    assert len(chunks) >= 1
    assert any("single block could not be safely split" in w for w in chunker.warnings)
