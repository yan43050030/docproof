"""Revision mode text display with red strikethrough + blue corrections."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor
from PySide6.QtWidgets import QTextEdit

from docproof.engine.base_engine import ErrorItem


class CorrectionView(QTextEdit):
    """Displays proofread text with revision markup.

    Review mode: read-only HTML with red strikethrough + blue corrections.
    Edit mode: editable plain text with error positions highlighted.
    """

    error_clicked = Signal(int)  # error index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(400)
        self._errors: list[ErrorItem] = []
        self._sorted_errors: list[ErrorItem] = []
        self._original_text = ""
        self._current_text = ""  # base + accepted corrections applied
        self._current_error_idx = -1
        self._edit_mode = False
        self._proofread_done = False

        font = QFont("PingFang SC, Microsoft YaHei, sans-serif", 13)
        self.setFont(font)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 16px;
                background: white;
                line-height: 1.8;
            }
        """)

    # ---- public API ----

    def load_text(self, text: str) -> None:
        """Display plain text in the view."""
        self._original_text = text
        self._current_text = text
        self._errors = []
        self._sorted_errors = []
        self._current_error_idx = -1
        self._proofread_done = False
        self._edit_mode = False
        self.setReadOnly(True)
        self.setPlainText(text)

    def show_corrections(self, text: str, errors: list[ErrorItem],
                         highlight_idx: int = -1) -> None:
        """Display text with revision markup for all errors (review mode)."""
        self._original_text = text
        self._current_text = text
        self._errors = errors
        self._sorted_errors = sorted(errors, key=lambda e: e.start)
        self._current_error_idx = highlight_idx
        self._proofread_done = True
        self._edit_mode = False
        self.setReadOnly(True)

        proportion = self._scroll_proportion()
        self.clear()

        if not errors:
            self.setHtml(
                f"<p style='color:#16A34A; font-size:14px;'>"
                f"✓ 未发现错误，文档很干净！</p>"
                f"<hr>"
                f"<p>{self._escape_html(text).replace(chr(10), '<br>')}</p>"
            )
            self._restore_scroll_proportion(proportion)
            return

        self._render_html(text, errors, highlight_idx)
        self._restore_scroll_proportion(proportion)

    def show_partial(self, base_text: str, all_errors: list[ErrorItem],
                     accepted_indices: set[int], highlight_idx: int = -1) -> None:
        """Display text with accepted corrections applied and remaining errors
        shown with markup. Error positions are adjusted for text length changes."""
        self._errors = all_errors

        if not accepted_indices:
            self._current_text = base_text
            self.show_corrections(base_text, all_errors, highlight_idx)
            return

        new_text, remaining_pairs = self._build_partial_text(
            base_text, all_errors, accepted_indices)

        self._current_text = new_text
        self._original_text = new_text
        remaining_errors = [e for _, e in remaining_pairs]
        self._sorted_errors = sorted(remaining_errors, key=lambda e: e.start)
        self._current_error_idx = highlight_idx

        proportion = self._scroll_proportion()
        self.clear()

        if not remaining_errors:
            self.setHtml(
                f"<p style='color:#16A34A; font-size:14px;'>"
                f"✓ 所有修改已接受！</p>"
                f"<hr>"
                f"<p>{self._escape_html(new_text).replace(chr(10), '<br>')}</p>"
            )
            self._restore_scroll_proportion(proportion)
            return

        self._render_html(new_text, remaining_errors, highlight_idx)
        self._restore_scroll_proportion(proportion)

    def highlight_error(self, error_idx: int) -> None:
        """Scroll to and highlight a specific error. Works in both modes."""
        if error_idx < 0 or error_idx >= len(self._errors):
            return

        err = self._errors[error_idx]

        if self._edit_mode:
            self._navigate_to_error_in_plain_text(err)
            return

        # Review mode: scroll to HTML anchor
        sorted_idx = self._find_sorted_index(err)
        if sorted_idx < 0:
            return
        self._current_error_idx = sorted_idx
        self.scrollToAnchor(f"err{sorted_idx}")

    def set_edit_mode(self, enabled: bool) -> None:
        """Toggle between read-only review mode and editable plain-text mode
        with error highlights."""
        if not self._proofread_done:
            return

        self._edit_mode = enabled
        proportion = self._scroll_proportion()

        if enabled:
            self.setReadOnly(False)
            self.setPlainText(self._current_text)
            self._apply_error_highlights()
        else:
            self.setReadOnly(True)
            self._restore_markup_view()

        self._restore_scroll_proportion(proportion)

    def get_edited_text(self) -> str:
        """Return the current text content."""
        if self._edit_mode:
            return self.toPlainText()
        return self._current_text

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    # ---- internal: text building ----

    @staticmethod
    def _build_partial_text(base_text: str, all_errors: list[ErrorItem],
                            accepted_indices: set[int]) -> tuple[str, list]:
        """Apply accepted corrections and return (new_text, remaining_pairs)."""
        sorted_pairs = sorted(enumerate(all_errors), key=lambda x: x[1].start)
        parts = []
        cursor = 0
        delta = 0
        remaining_pairs = []

        for orig_idx, err in sorted_pairs:
            if err.start > cursor:
                parts.append(base_text[cursor:err.start])

            if orig_idx in accepted_indices:
                parts.append(err.correct)
                delta += len(err.correct) - len(err.error)
            else:
                new_start = err.start + delta
                parts.append(err.error)
                remaining_pairs.append((orig_idx, ErrorItem(
                    error=err.error,
                    correct=err.correct,
                    start=new_start,
                    end=new_start + len(err.error),
                )))

            cursor = err.end

        if cursor < len(base_text):
            parts.append(base_text[cursor:])

        return ''.join(parts), remaining_pairs

    # ---- internal: navigation ----

    def _find_sorted_index(self, err: ErrorItem) -> int:
        """Find the index of an error in _sorted_errors."""
        try:
            return self._sorted_errors.index(err)
        except ValueError:
            pass
        for i, se in enumerate(self._sorted_errors):
            if se.error == err.error and se.correct == err.correct:
                return i
        return -1

    def _navigate_to_error_in_plain_text(self, err: ErrorItem) -> None:
        """In edit mode, move cursor to error position and select it."""
        pos = None
        for se in self._sorted_errors:
            if se.error == err.error and se.correct == err.correct:
                pos = se.start
                break
        if pos is None:
            pos = err.start

        cursor = self.textCursor()
        cursor.setPosition(pos)
        cursor.setPosition(pos + len(err.error), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    # ---- internal: rendering ----

    def _scroll_proportion(self) -> float:
        sb = self.verticalScrollBar()
        if sb.maximum() > 0:
            return sb.value() / sb.maximum()
        return 0.0

    def _restore_scroll_proportion(self, proportion: float) -> None:
        sb = self.verticalScrollBar()
        target = int(proportion * sb.maximum())
        sb.setValue(target)

    def _apply_error_highlights(self) -> None:
        """Apply red background + wavy underline to error positions in edit mode."""
        error_fmt = QTextCharFormat()
        error_fmt.setBackground(QColor("#FECACA"))  # light red
        error_fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        error_fmt.setUnderlineColor(QColor("#DC2626"))  # red
        error_fmt.setToolTip("")  # will be set per-error

        cursor = self.textCursor()
        for err in self._sorted_errors:
            fmt = QTextCharFormat(error_fmt)
            fmt.setToolTip(f"{err.error} → {err.correct}")
            cursor.setPosition(err.start)
            cursor.setPosition(err.end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    def _restore_markup_view(self) -> None:
        """Rebuild the markup view when exiting edit mode."""
        self.clear()
        if not self._errors:
            self.setPlainText(self._current_text)
            return
        self.setHtml(
            f"<p style='font-family: PingFang SC, Microsoft YaHei, sans-serif; "
            f"font-size: 13px; line-height: 2.0;'>"
            f"{self._escape_html(self._current_text).replace(chr(10), '<br>')}"
            f"</p>"
        )

    def _render_html(self, text: str, errors: list[ErrorItem],
                     highlight_idx: int) -> None:
        """Build and set HTML for text with errors marked up."""
        sorted_errors = sorted(errors, key=lambda e: e.start)
        cursor = 0
        parts = []

        for i, err in enumerate(sorted_errors):
            if err.start > cursor:
                parts.append(self._escape_html(text[cursor:err.start]))

            error_text = self._escape_html(err.error)
            correct_text = self._escape_html(err.correct)
            hl = "background-color: #FEF08A; border-radius: 2px;" if i == highlight_idx else ""

            parts.append(
                f'<a name="err{i}"></a>'
                f'<span style="{hl}">'
                f'<span style="color:#DC2626;text-decoration:line-through;" '
                f'title="建议改为: {correct_text}">'
                f'{error_text}</span>'
                f'</span>'
            )

            cursor = err.end

        if cursor < len(text):
            parts.append(self._escape_html(text[cursor:]))

        html = f"""
        <p style="font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
                  font-size: 13px; line-height: 2.0;">
            {''.join(parts).replace(chr(10), '<br>')}
        </p>
        """
        self.setHtml(html)

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @property
    def error_count(self) -> int:
        return len(self._errors)
