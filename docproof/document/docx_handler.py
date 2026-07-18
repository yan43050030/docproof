"""Read, proofread, and write Word (.docx) documents with format preservation.

Uses python-docx for document manipulation and PositionMapper for locating
corrections at the run level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docx.document import Document as DocumentType

from docx import Document
from docx.shared import RGBColor

from docproof.document.position_mapper import PositionMapper


@dataclass
class CorrectionResult:
    """Result of proofreading a document."""

    original_text: str
    corrected_text: str
    errors: list = field(default_factory=list)  # list of ErrorItem
    paragraph_errors: dict[int, list] = field(default_factory=dict)
    # paragraph_index -> list of ErrorItem


class DocxHandler:
    """Handles .docx document reading, correction application, and writing."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._doc: DocumentType | None = None
        self._mapper = PositionMapper()
        self._result: CorrectionResult | None = None

    @property
    def document(self):
        return self._doc

    @property
    def paragraphs(self) -> list:
        if self._doc:
            return list(self._doc.paragraphs)
        return []

    @property
    def mapper(self) -> PositionMapper:
        return self._mapper

    @property
    def result(self) -> CorrectionResult | None:
        return self._result

    def load(self) -> None:
        """Open and parse the document."""
        self._doc = Document(self.filepath)
        self._mapper.build(list(self._doc.paragraphs))

    def get_full_text(self) -> str:
        """Get the full text content of the document."""
        if not self._doc:
            raise RuntimeError("Document not loaded. Call load() first.")
        # Use paragraph texts joined by newlines for engine processing
        return "\n".join(self._mapper._paragraph_texts)

    def apply_corrections(
        self, errors: list, markup: bool = True
    ) -> CorrectionResult:
        """
        Apply corrections to the document.

        Args:
            errors: List of ErrorItem objects from the proofreading engine.
            markup: If True, add revision markup (red strikethrough + blue correction).
                    If False, directly replace error text with correction.

        Returns:
            CorrectionResult with details.
        """
        if not self._doc:
            raise RuntimeError("Document not loaded. Call load() first.")

        # Group errors by paragraph
        paragraph_errors: dict[int, list] = {}
        for err in errors:
            span = self._mapper.char_to_span(err.start)
            if span is None:
                continue
            p_idx = span.paragraph_index
            if p_idx not in paragraph_errors:
                paragraph_errors[p_idx] = []
            paragraph_errors[p_idx].append(err)

        # Sort errors within each paragraph by position (descending to avoid offset issues)
        for p_idx in paragraph_errors:
            paragraph_errors[p_idx].sort(key=lambda e: e.start, reverse=True)

        # Track results
        all_original = self.get_full_text()
        result = CorrectionResult(
            original_text=all_original,
            corrected_text=all_original,
            errors=errors,
            paragraph_errors=paragraph_errors,
        )

        # Apply corrections to each paragraph
        for p_idx, p_errors in paragraph_errors.items():
            para, runs, para_start, para_end = self._mapper._paragraph_info[p_idx]
            for err in p_errors:
                local_start = err.start - para_start
                local_end = err.end - para_start

                if markup:
                    self._apply_markup(para, runs, local_start, local_end,
                                       err.error, err.correct)
                else:
                    self._apply_direct_replace(runs, local_start, local_end,
                                               err.correct)

        # Build corrected full text
        if markup:
            result.corrected_text = "\n".join(
                p.text for p in self._doc.paragraphs
            )
        else:
            result.corrected_text = self.get_full_text()

        self._result = result
        return result

    def _apply_markup(
        self, para, runs: list, start: int, end: int,
        error_word: str, correct_word: str
    ) -> None:
        """Add revision markup: red strikethrough for error, blue for correction."""
        # Clear the paragraph and rebuild with markup
        # Get the full text
        full_text = para.text

        # Split: before_error + [error] + after_error
        before = full_text[:start]
        after = full_text[end:]

        # Clear all runs
        for run in runs:
            run.text = ""

        # Rebuild: use first run for all text with formatting
        if not runs:
            return

        # Write: before (normal) + error (red strikethrough) + correct (blue bold)
        runs[0].text = before

        # Add error word
        from docx.oxml.ns import qn
        error_run = para.add_run(error_word)
        error_run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)  # red
        error_run.font.strike = True

        # Add " → "
        arrow_run = para.add_run(" → ")
        arrow_run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        arrow_run.font.size = error_run.font.size

        # Add correction
        correct_run = para.add_run(correct_word)
        correct_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)  # blue
        correct_run.font.bold = True

        # Add remaining text
        after_run = para.add_run(after)

    def _apply_direct_replace(
        self, runs: list, start: int, end: int, replacement: str
    ) -> None:
        """Directly replace text in runs without markup."""
        current_pos = 0
        for run in runs:
            run_text = run.text
            run_len = len(run_text)
            run_end = current_pos + run_len

            if current_pos <= start < run_end:
                # This run contains the start of the error
                offset_in_run = start - current_pos
                if end <= run_end:
                    # Error is entirely within this run
                    run.text = (
                        run_text[:offset_in_run]
                        + replacement
                        + run_text[offset_in_run + (end - start):]
                    )
                    return
                else:
                    # Error spans multiple runs (handle start)
                    run.text = run_text[:offset_in_run] + replacement
                    # Remove text from subsequent runs
                    remaining = end - run_end
                    # Fall through to handle remaining runs

            elif start < current_pos and end > current_pos:
                # This run is entirely within the error range
                chars_to_remove = min(run_len, end - current_pos)
                run.text = run_text[chars_to_remove:]

            current_pos = run_end

    def save(self, filepath: str) -> None:
        """Save the document to a new file."""
        if not self._doc:
            raise RuntimeError("Document not loaded.")
        self._doc.save(filepath)

    def export_clean(self, filepath: str) -> None:
        """Export a clean version with all corrections applied (no markup)."""
        for p_idx, p_errors in (self._result.paragraph_errors.items()
                                if self._result else {}):
            para, runs, para_start, para_end = self._mapper._paragraph_info[p_idx]
            # Clear the markup added by _apply_markup (extra runs from index 1)
            original_text = para.text
            # Re-apply as direct replace
            pass

        # Simpler approach: reload original and apply without markup
        original = Document(self.filepath)
        from docproof.document.position_mapper import PositionMapper
        temp_mapper = PositionMapper()
        temp_mapper.build(list(original.paragraphs))

        if self._result:
            for p_idx, p_errors in self._result.paragraph_errors.items():
                para = original.paragraphs[p_idx]
                runs = list(para.runs)
                _, _, para_start, para_end = temp_mapper._paragraph_info[p_idx]
                for err in sorted(p_errors, key=lambda e: e.start, reverse=True):
                    local_start = err.start - para_start
                    local_end = err.end - para_start
                    self._apply_direct_replace(
                        runs, local_start, local_end, err.correct
                    )

        original.save(filepath)
