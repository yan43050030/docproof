"""Maps character positions to document structure for format-preserving edits.

python-docx stores text in runs (contiguous same-formatting segments) within paragraphs.
To replace text without losing formatting, we need to map character offsets back to
specific runs and offsets within those runs.
"""

from dataclasses import dataclass

from docx.text.paragraph import Paragraph
from docx.text.run import Run


@dataclass
class TextSpan:
    """Identifies a span of text within a specific run of a paragraph."""

    paragraph_index: int
    run_index: int
    offset_in_run: int


class PositionMapper:
    """Builds and queries a character-position → document-location mapping."""

    def __init__(self):
        # _map[char_pos] = TextSpan for the character at that global position
        self._map: list[TextSpan] = []
        # _paragraphs[i] = (Paragraph, list_of_runs, start_char, end_char)
        self._paragraph_info: list[tuple[Paragraph, list[Run], int, int]] = []
        # Total character count (including paragraph separators)
        self._total_chars: int = 0
        # Paragraph texts (for matching)
        self._paragraph_texts: list[str] = []

    def build(self, paragraphs: list[Paragraph]) -> None:
        """Build the mapping from a list of python-docx Paragraph objects."""
        self._map = []
        self._paragraph_info = []
        self._paragraph_texts = []
        char_pos = 0

        for p_idx, para in enumerate(paragraphs):
            runs = list(para.runs)
            para_start = char_pos

            for r_idx, run in enumerate(runs):
                text = run.text
                for c_idx in range(len(text)):
                    self._map.append(TextSpan(
                        paragraph_index=p_idx,
                        run_index=r_idx,
                        offset_in_run=c_idx,
                    ))
                    char_pos += 1

            para_end = char_pos
            para_text = para.text
            self._paragraph_info.append((para, runs, para_start, para_end))
            self._paragraph_texts.append(para_text)

            # Add newline separator between paragraphs (not in any run)
            char_pos += 1

        self._total_chars = char_pos

    def char_to_span(self, char_pos: int) -> TextSpan | None:
        """Map a global character position to a document span."""
        if 0 <= char_pos < len(self._map):
            return self._map[char_pos]
        return None

    def get_paragraph_range(self, paragraph_index: int) -> tuple[int, int]:
        """Get (start, end) character positions for a paragraph."""
        if 0 <= paragraph_index < len(self._paragraph_info):
            _, _, start, end = self._paragraph_info[paragraph_index]
            return start, end
        return 0, 0

    def get_paragraph_text(self, paragraph_index: int) -> str:
        """Get the full text of a paragraph."""
        if 0 <= paragraph_index < len(self._paragraph_texts):
            return self._paragraph_texts[paragraph_index]
        return ""

    @property
    def paragraph_count(self) -> int:
        return len(self._paragraph_info)

    @property
    def total_chars(self) -> int:
        return self._total_chars
