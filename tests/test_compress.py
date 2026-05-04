from types import SimpleNamespace

import pytest

from doc_preprocessor.chunk import Chunk
from doc_preprocessor.compress import LLMCompressor, MISSING_LLMLINGUA_MSG


def test_missing_dependency_raises(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    with pytest.raises(RuntimeError, match=MISSING_LLMLINGUA_MSG):
        LLMCompressor().compress_chunks([])


def test_compression_enabled_path(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: SimpleNamespace())

    class FakePromptCompressor:
        def compress_prompt(self, text, **kwargs):
            return {"compressed_prompt": text[:10]}

    import sys

    sys.modules["llmlingua"] = SimpleNamespace(PromptCompressor=FakePromptCompressor)
    chunks = [Chunk(id="c1", heading="H", text="abcdefghijklmno", estimated_tokens=4)]
    out, stats = LLMCompressor(compression_ratio=0.5).compress_chunks(chunks)
    assert len(out) == 1
    assert out[0].text == "abcdefghij"
    assert stats.post_compression_tokens <= stats.pre_compression_tokens
