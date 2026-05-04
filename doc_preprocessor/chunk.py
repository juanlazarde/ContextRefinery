"""Markdown structure-aware chunking."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re

from .estimate import TokenEstimator


@dataclass
class Chunk:
    id: str
    heading: str
    text: str
    estimated_tokens: int

    def to_dict(self) -> dict:
        return asdict(self)


class MarkdownChunker:
    """Chunk markdown by headings with optional max token constraints."""

    HEADING_RE = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")

    def __init__(self, max_chunk_tokens: int | None = None):
        self.max_chunk_tokens = max_chunk_tokens
        self.warnings: list[str] = []

    def chunk(self, text: str) -> list[Chunk]:
        sections = self._to_sections(text)
        chunks: list[Chunk] = []
        idx = 1
        for heading, body in sections:
            if self.max_chunk_tokens is None:
                token_count = TokenEstimator.estimate(body)
                chunks.append(Chunk(id=f"chunk_{idx:04d}", heading=heading, text=body, estimated_tokens=token_count))
                idx += 1
                continue

            for piece in self._split_section_safely(body):
                token_count = TokenEstimator.estimate(piece)
                chunks.append(Chunk(id=f"chunk_{idx:04d}", heading=heading, text=piece, estimated_tokens=token_count))
                idx += 1
        return chunks

    def _to_sections(self, text: str) -> list[tuple[str, str]]:
        lines = text.split("\n")
        sections: list[tuple[str, list[str]]] = []
        current_heading = "Preamble"
        current_lines: list[str] = []

        for line in lines:
            m = self.HEADING_RE.match(line)
            if m:
                if current_lines:
                    sections.append((current_heading, current_lines))
                current_heading = m.group(2).strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        return [(h, "\n".join(ls).strip()) for h, ls in sections if "\n".join(ls).strip()]

    def _split_section_safely(self, text: str) -> list[str]:
        max_tokens = self.max_chunk_tokens
        if max_tokens is None:
            return [text]

        blocks = self._extract_blocks(text)
        out: list[str] = []
        current: list[str] = []

        for block in blocks:
            block_tokens = TokenEstimator.estimate(block)
            if block_tokens > max_tokens:
                if current:
                    out.append("\n\n".join(current).strip())
                    current = []
                out.append(block)
                self.warnings.append(
                    "Chunk exceeds max because a single block could not be safely split."
                )
                continue

            tentative = "\n\n".join(current + [block]).strip() if current else block
            if TokenEstimator.estimate(tentative) <= max_tokens:
                current.append(block)
            else:
                if current:
                    out.append("\n\n".join(current).strip())
                current = [block]

        if current:
            out.append("\n\n".join(current).strip())

        return [x for x in out if x.strip()]

    def _extract_blocks(self, text: str) -> list[str]:
        lines = text.split("\n")
        blocks: list[str] = []
        i = 0
        while i < len(lines):
            if not lines[i].strip():
                i += 1
                continue

            if self._is_table_line(lines[i]):
                start = i
                i += 1
                while i < len(lines) and self._is_table_line(lines[i]):
                    i += 1
                blocks.append("\n".join(lines[start:i]).strip())
                continue

            para: list[str] = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip() and not self._is_table_line(lines[i]):
                para.append(lines[i])
                i += 1
            blocks.append("\n".join(para).strip())

        return blocks

    @staticmethod
    def _is_table_line(line: str) -> bool:
        s = line.strip()
        return s.startswith("|") and s.endswith("|") and "|" in s[1:-1]
