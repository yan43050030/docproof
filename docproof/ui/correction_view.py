"""Text view showing proofreading results.

Rendering uses plain text plus QTextCharFormat spans instead of HTML. This is
much faster than setHtml on large documents, and — because QTextEdit counts a
block separator as one character exactly like our "\\n" — display positions map
1:1 to engine text offsets. That exact mapping powers click-to-select: clicking
an error in the text selects it in the error list.

Modes:
* review mode — read-only, errors shown in red strikethrough with a light red
  background; the currently selected error gets a yellow highlight.
* edit mode — editable plain text with error positions underlined.
"""

from __future__ import annotations

import bisect

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from docproof.engine.base_engine import ErrorItem

# span: (original_error_index, start, end, error_text, correct_text)
_Span = tuple[int, int, int, str, str]


def _error_format(highlight: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#DC2626"))
    fmt.setFontStrikeOut(True)
    fmt.setBackground(QColor("#FEF08A") if highlight else QColor("#FEE2E2"))
    return fmt


def _edit_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setBackground(QColor("#FECACA"))
    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
    fmt.setUnderlineColor(QColor("#DC2626"))
    return fmt


class CorrectionView(QTextEdit):
    """Displays proofread text with error markup and exact click mapping."""

    error_clicked = Signal(int)  # original error index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(400)
        self._errors: list[ErrorItem] = []      # full original list
        self._spans: list[_Span] = []            # displayed spans, sorted by start
        self._span_starts: list[int] = []        # for bisect click lookup
        self._current_text = ""
        self._highlighted: int | None = None     # original index of highlighted err
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
            }
        """)

    # ---- public API ----

    def load_text(self, text: str) -> None:
        """Display plain text with no markup."""
        self._current_text = text
        self._errors = []
        self._spans = []
        self._span_starts = []
        self._highlighted = None
        self._proofread_done = False
        self._edit_mode = False
        self.setReadOnly(True)
        self.setPlainText(text)

    def show_corrections(self, text: str, errors: list[ErrorItem],
                         highlight_idx: int = -1) -> None:
        """Display text with all errors marked (review mode)."""
        self._errors = errors
        self._proofread_done = True
        self._edit_mode = False
        self.setReadOnly(True)

        spans = [(i, e.start, e.end, e.error, e.correct)
                 for i, e in enumerate(errors)]
        spans.sort(key=lambda s: s[1])
        self._render(text, spans, highlight_idx)

    def show_partial(self, base_text: str, all_errors: list[ErrorItem],
                     accepted_indices: set[int], highlight_idx: int = -1) -> None:
        """Display text with accepted corrections applied and the remaining
        errors marked at their adjusted positions."""
        self._errors = all_errors
        self._proofread_done = True
        self._edit_mode = False
        self.setReadOnly(True)

        if not accepted_indices:
            self.show_corrections(base_text, all_errors, highlight_idx)
            return

        new_text, spans = self._build_partial(base_text, all_errors,
                                              accepted_indices)
        self._render(new_text, spans, highlight_idx)

    def add_errors(self, text: str, errors: list[ErrorItem]) -> None:
        """Incrementally mark newly found errors (streaming results).

        ``errors`` must be the full list so far; only unrendered spans are
        formatted, keeping per-batch cost proportional to the batch size.
        """
        if self.toPlainText() != text or not self._proofread_done:
            self.show_corrections(text, errors)
            return
        known = {s[0] for s in self._spans}
        self._errors = errors
        new_spans = [(i, e.start, e.end, e.error, e.correct)
                     for i, e in enumerate(errors) if i not in known]
        base_fmt = _error_format(False)
        for span in new_spans:
            self._apply_span_format(span, base_fmt)
        self._spans.extend(new_spans)
        self._spans.sort(key=lambda s: s[1])
        self._span_starts = [s[1] for s in self._spans]

    def highlight_error(self, error_idx: int) -> None:
        """Scroll to and highlight a specific error (by original index)."""
        if error_idx < 0 or error_idx >= len(self._errors):
            return

        if self._edit_mode:
            span = self._find_span(error_idx)
            if span:
                self._select_range(span[1], span[2])
            return

        # Un-highlight the previous one, highlight the new one.
        if self._highlighted is not None and self._highlighted != error_idx:
            prev = self._find_span(self._highlighted)
            if prev:
                self._apply_span_format(prev, _error_format(False))
        span = self._find_span(error_idx)
        if span is None:
            return
        self._apply_span_format(span, _error_format(True))
        self._highlighted = error_idx

        cursor = self.textCursor()
        cursor.setPosition(span[1])
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def set_edit_mode(self, enabled: bool) -> None:
        """Toggle between read-only review mode and editable plain text."""
        if not self._proofread_done:
            return
        self._edit_mode = enabled
        proportion = self._scroll_proportion()
        if enabled:
            self.setReadOnly(False)
            self.setPlainText(self._current_text)
            fmt = _edit_format()
            for span in self._spans:
                self._apply_span_format(span, fmt)
        else:
            self.setReadOnly(True)
        self._restore_scroll_proportion(proportion)

    def get_edited_text(self) -> str:
        if self._edit_mode:
            return self.toPlainText()
        return self._current_text

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    @property
    def error_count(self) -> int:
        return len(self._errors)

    # ---- zoom ----

    def zoom_in(self) -> None:
        self.zoomIn(1)

    def zoom_out(self) -> None:
        self.zoomOut(1)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    # ---- click-to-select ----

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._edit_mode or not self._proofread_done:
            return
        pos = self.cursorForPosition(event.position().toPoint()).position()
        i = bisect.bisect_right(self._span_starts, pos) - 1
        if 0 <= i < len(self._spans):
            orig_idx, start, end, _, _ = self._spans[i]
            if start <= pos < end:
                self.error_clicked.emit(orig_idx)

    # ---- internal ----

    def _render(self, text: str, spans: list[_Span], highlight_idx: int) -> None:
        proportion = self._scroll_proportion()
        self._current_text = text
        self._spans = spans
        self._span_starts = [s[1] for s in spans]
        self._highlighted = None

        self.setPlainText(text)
        base_fmt = _error_format(False)
        for span in spans:
            self._apply_span_format(span, base_fmt)
        self._restore_scroll_proportion(proportion)

        if highlight_idx >= 0:
            self.highlight_error(highlight_idx)

    def _apply_span_format(self, span: _Span, fmt: QTextCharFormat) -> None:
        orig_idx, start, end, error, correct = span
        f = QTextCharFormat(fmt)
        f.setToolTip(f"{error} → {correct if correct else '（删除）'}")
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.setCharFormat(f)

    def _find_span(self, orig_idx: int) -> _Span | None:
        for span in self._spans:
            if span[0] == orig_idx:
                return span
        return None

    def _select_range(self, start: int, end: int) -> None:
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    @staticmethod
    def _build_partial(base_text: str, all_errors: list[ErrorItem],
                       accepted_indices: set[int]) -> tuple[str, list[_Span]]:
        """Apply accepted corrections; return (new_text, remaining spans)."""
        ordered = sorted(enumerate(all_errors), key=lambda x: x[1].start)
        parts: list[str] = []
        spans: list[_Span] = []
        cursor = 0
        delta = 0
        for orig_idx, err in ordered:
            if err.start > cursor:
                parts.append(base_text[cursor:err.start])
            if orig_idx in accepted_indices:
                parts.append(err.correct)
                delta += len(err.correct) - len(err.error)
            else:
                new_start = err.start + delta
                spans.append((orig_idx, new_start, new_start + len(err.error),
                              err.error, err.correct))
                parts.append(err.error)
            cursor = err.end
        if cursor < len(base_text):
            parts.append(base_text[cursor:])
        return "".join(parts), spans

    def _scroll_proportion(self) -> float:
        sb = self.verticalScrollBar()
        if sb.maximum() > 0:
            return sb.value() / sb.maximum()
        return 0.0

    def _restore_scroll_proportion(self, proportion: float) -> None:
        sb = self.verticalScrollBar()
        sb.setValue(int(proportion * sb.maximum()))
