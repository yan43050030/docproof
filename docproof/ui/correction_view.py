"""Revision mode text display with red strikethrough + blue corrections."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor
from PySide6.QtWidgets import QTextEdit

from docproof.engine.base_engine import ErrorItem


class CorrectionView(QTextEdit):
    """Displays proofread text with revision markup.

    Error words are shown in red with strikethrough, followed by blue bold corrections.
    """

    error_clicked = Signal(int)  # error index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(400)
        self._errors: list[ErrorItem] = []
        self._original_text = ""
        self._current_error_idx = -1

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

    def load_text(self, text: str) -> None:
        """Display plain text in the view."""
        self._original_text = text
        self._errors = []
        self._current_error_idx = -1
        self.setPlainText(text)

    def show_corrections(self, text: str, errors: list[ErrorItem]) -> None:
        """Display text with revision markup for each error."""
        self._original_text = text
        self._errors = errors
        self.clear()

        if not errors:
            self.setHtml(
                f"<p style='color:#16A34A; font-size:14px;'>"
                f"✓ 未发现错误，文档很干净！</p>"
                f"<hr>"
                f"<p>{text.replace(chr(10), '<br>')}</p>"
            )
            return

        # Sort errors by position
        sorted_errors = sorted(errors, key=lambda e: e.start)

        # Build HTML with error markup
        cursor = 0
        parts = []
        for i, err in enumerate(sorted_errors):
            # Text before this error
            if err.start > cursor:
                before = self._escape_html(text[cursor:err.start])
                parts.append(before)

            # Error: red strikethrough + blue correction
            error_text = self._escape_html(err.error)
            correct_text = self._escape_html(err.correct)
            parts.append(
                f'<span style="color:#DC2626;text-decoration:line-through;" '
                f'title="错误 #{i+1}: {error_text} → {correct_text}">'
                f'{error_text}</span>'
                f'<span style="color:#2563EB;font-weight:bold;" '
                f'title="建议改为: {correct_text}">'
                f'{correct_text}</span>'
            )

            cursor = err.end

        # Remaining text
        if cursor < len(text):
            parts.append(self._escape_html(text[cursor:]))

        html = f"""
        <p style="font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
                  font-size: 13px; line-height: 2.0;">
            {''.join(parts).replace(chr(10), '<br>')}
        </p>
        """
        self.setHtml(html)

    def highlight_error(self, error_idx: int) -> None:
        """Scroll to and highlight a specific error."""
        if error_idx < 0 or error_idx >= len(self._errors):
            return
        self._current_error_idx = error_idx

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @property
    def error_count(self) -> int:
        return len(self._errors)
