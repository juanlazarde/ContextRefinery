"""Deterministic document cleaning with loss audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re


@dataclass
class RemovalAudit:
    page_numbers_count: int = 0
    duplicate_paragraphs_count: int = 0
    repeated_headers: list[str] = field(default_factory=list)
    repeated_footers: list[str] = field(default_factory=list)
    removed_lines_sample: list[str] = field(default_factory=list)
    duplicate_paragraph_samples: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CleanResult:
    cleaned_text: str
    removed: RemovalAudit


class DocumentCleaner:
    """Deterministic cleaner for structured docs."""

    PAGE_NUMBER_PATTERNS = [
        re.compile(r"^\s*page\s+\d+\s*$", re.IGNORECASE),
        re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
        re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
        re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$"),
    ]

    def __init__(self, aggressive: bool = False, sample_limit: int = 20):
        self.aggressive = aggressive
        self.sample_limit = sample_limit

    def clean(self, text: str) -> CleanResult:
        audit = RemovalAudit()
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.rstrip() for ln in text.split("\n")]

        segments = self._segment_pages(lines)
        repeated_headers, repeated_footers = self._detect_repeated_header_footer(segments)
        audit.repeated_headers = sorted(repeated_headers)
        audit.repeated_footers = sorted(repeated_footers)

        cleaned_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped in repeated_headers or stripped in repeated_footers:
                self._sample_line(audit.removed_lines_sample, line)
                continue
            if self._is_page_number_line(line):
                audit.page_numbers_count += 1
                self._sample_line(audit.removed_lines_sample, line)
                continue
            if self._is_noise_line(line):
                self._sample_line(audit.removed_lines_sample, line)
                continue
            cleaned_lines.append(line)

        cleaned_text = self._collapse_blank_lines("\n".join(cleaned_lines)).strip()
        deduped_text, dedup_count, dup_samples = self._remove_duplicate_paragraphs(cleaned_text)
        audit.duplicate_paragraphs_count = dedup_count
        audit.duplicate_paragraph_samples = dup_samples

        return CleanResult(cleaned_text=deduped_text, removed=audit)

    def _segment_pages(self, lines: list[str]) -> list[list[str]]:
        text = "\n".join(lines)
        if "\f" in text:
            raw_segments = [seg.split("\n") for seg in text.split("\f")]
            return [seg for seg in raw_segments if any(x.strip() for x in seg)]

        if len(lines) < 120:
            return [lines]

        size = 60
        segments = [lines[i : i + size] for i in range(0, len(lines), size)]
        return [seg for seg in segments if any(x.strip() for x in seg)]

    def _detect_repeated_header_footer(
        self, segments: list[list[str]]
    ) -> tuple[set[str], set[str]]:
        threshold = 2 if self.aggressive else 3
        header_counts: dict[str, int] = {}
        footer_counts: dict[str, int] = {}

        for seg in segments:
            non_empty = [ln.strip() for ln in seg if ln.strip()]
            if not non_empty:
                continue
            window = 5 if self.aggressive else 3
            for ln in non_empty[:window]:
                if self._eligible_repeated_line(ln):
                    header_counts[ln] = header_counts.get(ln, 0) + 1
            for ln in non_empty[-window:]:
                if self._eligible_repeated_line(ln):
                    footer_counts[ln] = footer_counts.get(ln, 0) + 1

        headers = {ln for ln, c in header_counts.items() if c >= threshold}
        footers = {ln for ln, c in footer_counts.items() if c >= threshold}
        return headers, footers

    def _eligible_repeated_line(self, line: str) -> bool:
        if len(line) > (120 if self.aggressive else 90):
            return False
        if "|" in line:
            return False
        if re.match(r"^#{1,6}\s+", line):
            return False
        digits = sum(ch.isdigit() for ch in line)
        letters = sum(ch.isalpha() for ch in line)
        if not self.aggressive and digits > 0:
            return False
        return letters >= 3

    def _is_page_number_line(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        return any(p.match(s) for p in self.PAGE_NUMBER_PATTERNS)

    def _is_noise_line(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if re.fullmatch(r"[_\-*~=]{4,}", s):
            return True
        if re.fullmatch(r"[•·]{3,}", s):
            return True
        return False

    def _collapse_blank_lines(self, text: str) -> str:
        text = re.sub(r"\n[ \t]+\n", "\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _remove_duplicate_paragraphs(self, text: str) -> tuple[str, int, list[str]]:
        paragraphs = re.split(r"\n\s*\n", text)
        seen: set[str] = set()
        kept: list[str] = []
        dup_count = 0
        dup_samples: list[str] = []

        for para in paragraphs:
            normalized = re.sub(r"\s+", " ", para).strip()
            if not normalized:
                continue
            key = sha256(normalized.lower().encode("utf-8")).hexdigest()
            if key in seen:
                dup_count += 1
                if len(dup_samples) < self.sample_limit:
                    dup_samples.append(normalized[:200])
                continue
            seen.add(key)
            kept.append(para.strip())

        return "\n\n".join(kept), dup_count, dup_samples

    def _sample_line(self, sample: list[str], line: str) -> None:
        stripped = line.strip()
        if stripped and len(sample) < self.sample_limit:
            sample.append(stripped[:200])
