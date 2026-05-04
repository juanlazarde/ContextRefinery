"""Optional LLMLingua compression."""

from __future__ import annotations

from dataclasses import dataclass
import importlib

from .chunk import Chunk
from .estimate import TokenEstimator


MISSING_LLMLINGUA_MSG = "LLMLingua not installed. Run: pip install llmlingua"


@dataclass
class CompressionStats:
    pre_compression_tokens: int
    post_compression_tokens: int
    compression_ratio_actual: float


class LLMCompressor:
    """Per-chunk compression using LLMLingua."""

    def __init__(self, target_tokens: int | None = None, compression_ratio: float | None = None):
        self.target_tokens = target_tokens
        self.compression_ratio = compression_ratio

    def compress_chunks(self, chunks: list[Chunk]) -> tuple[list[Chunk], CompressionStats]:
        llm_mod = importlib.util.find_spec("llmlingua")
        if llm_mod is None:
            raise RuntimeError(MISSING_LLMLINGUA_MSG)

        from llmlingua import PromptCompressor  # type: ignore

        compressor = PromptCompressor()
        pre_tokens = sum(ch.estimated_tokens for ch in chunks)
        total_target = self.target_tokens

        compressed_chunks: list[Chunk] = []
        for ch in chunks:
            kwargs = {}
            if self.compression_ratio is not None:
                kwargs["rate"] = self.compression_ratio
            if total_target is not None and pre_tokens > 0:
                chunk_target = max(1, int(total_target * (ch.estimated_tokens / pre_tokens)))
                kwargs["target_token"] = chunk_target
            result = compressor.compress_prompt(ch.text, **kwargs)
            new_text = self._extract_text(result)
            compressed_chunks.append(
                Chunk(
                    id=ch.id,
                    heading=ch.heading,
                    text=new_text,
                    estimated_tokens=TokenEstimator.estimate(new_text),
                )
            )

        post_tokens = sum(ch.estimated_tokens for ch in compressed_chunks)
        ratio = (post_tokens / pre_tokens) if pre_tokens else 1.0
        return compressed_chunks, CompressionStats(pre_tokens, post_tokens, ratio)

    def _extract_text(self, result) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("compressed_prompt", "prompt", "text"):
                val = result.get(key)
                if isinstance(val, str):
                    return val
        for attr in ("compressed_prompt", "prompt", "text"):
            val = getattr(result, attr, None)
            if isinstance(val, str):
                return val
        return str(result)
