"""Maps character positions to document structure for format-preserving edits.

python-docx stores text in runs (contiguous same-formatting segments) within
paragraphs. To replace text without losing formatting, we map a global character
offset back to a specific run and the offset within that run.

The "proofread text" of a paragraph is defined as the concatenation of its run
texts (``"".join(r.text for r in para.runs)``). Character offsets therefore align
exactly with editable runs, which keeps the proofreading pipeline and the
correction pipeline perfectly consistent.

Lookups use binary search over paragraph/run ranges — O(log n) per query and no
per-character bookkeeping, so large documents stay cheap.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any


@dataclass
class TextSpan:
    """Identifies a span of text within a specific run of a paragraph."""

    paragraph_index: int
    run_index: int
    offset_in_run: int


@dataclass
class _ParaEntry:
    """Cached layout information for a single paragraph."""

    para: Any
    runs: list
    run_starts: list[int]  # cumulative local start offset of each run
    text: str
    start: int  # global start offset
    end: int  # global end offset (exclusive), == start + len(text)


def paragraph_text(para) -> str:
    """The proofread text of a paragraph: concatenation of its run texts."""
    return "".join((r.text or "") for r in para.runs)


class PositionMapper:
    """Builds and queries a character-position -> document-location mapping."""

    def __init__(self):
        self._entries: list[_ParaEntry] = []
        self._starts: list[int] = []  # global start of each paragraph (for bisect)
        self._total_chars: int = 0

    # ---- build ----

    def build(self, paragraphs: list) -> None:
        """Build the mapping from an ordered list of python-docx paragraphs."""
        self._entries = []
        self._starts = []
        char_pos = 0

        for para in paragraphs:
            runs = list(para.runs)
            run_starts = []
            local = 0
            for run in runs:
                run_starts.append(local)
                local += len(run.text or "")
            text = "".join((r.text or "") for r in runs)

            entry = _ParaEntry(
                para=para,
                runs=runs,
                run_starts=run_starts,
                text=text,
                start=char_pos,
                end=char_pos + len(text),
            )
            self._entries.append(entry)
            self._starts.append(char_pos)

            # Reserve one position for the paragraph separator ("\n").
            char_pos = entry.end + 1

        self._total_chars = char_pos if self._entries else 0

    # ---- queries ----

    def _para_index_for(self, char_pos: int) -> int | None:
        """Return the paragraph index whose body contains char_pos, else None.

        Positions that fall on a paragraph separator ("\\n") return None.
        """
        if char_pos < 0 or not self._entries:
            return None
        # Rightmost paragraph whose start <= char_pos.
        i = bisect.bisect_right(self._starts, char_pos) - 1
        if i < 0:
            return None
        entry = self._entries[i]
        if entry.start <= char_pos < entry.end:
            return i
        # Empty paragraph: start == end, a single valid position at start.
        if entry.start == entry.end and char_pos == entry.start:
            return i
        return None

    def char_to_span(self, char_pos: int) -> TextSpan | None:
        """Map a global character position to a document span."""
        p_idx = self._para_index_for(char_pos)
        if p_idx is None:
            return None
        entry = self._entries[p_idx]
        local = char_pos - entry.start
        if not entry.run_starts:
            return TextSpan(p_idx, 0, 0)
        r_idx = bisect.bisect_right(entry.run_starts, local) - 1
        if r_idx < 0:
            r_idx = 0
        return TextSpan(p_idx, r_idx, local - entry.run_starts[r_idx])

    def get_paragraph(self, paragraph_index: int):
        """Return the python-docx Paragraph object at the given index."""
        if 0 <= paragraph_index < len(self._entries):
            return self._entries[paragraph_index].para
        return None

    def get_paragraph_range(self, paragraph_index: int) -> tuple[int, int]:
        """Get (start, end) character positions for a paragraph."""
        if 0 <= paragraph_index < len(self._entries):
            e = self._entries[paragraph_index]
            return e.start, e.end
        return 0, 0

    def get_paragraph_text(self, paragraph_index: int) -> str:
        """Get the proofread text of a paragraph."""
        if 0 <= paragraph_index < len(self._entries):
            return self._entries[paragraph_index].text
        return ""

    @property
    def paragraph_texts(self) -> list[str]:
        return [e.text for e in self._entries]

    @property
    def paragraphs(self) -> list:
        return [e.para for e in self._entries]

    @property
    def paragraph_count(self) -> int:
        return len(self._entries)

    @property
    def total_chars(self) -> int:
        return self._total_chars
