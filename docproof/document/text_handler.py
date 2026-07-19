"""Plain-text (.txt / .md) proofreading handler.

Provides the subset of the :class:`DocxHandler` interface the UI relies on so
plain-text files flow through the same load -> proofread -> export pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CorrectionResult:
    original_text: str
    corrected_text: str
    errors: list = field(default_factory=list)


class TextHandler:
    """Load, correct and save plain-text documents."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._text: str = ""
        self._result: CorrectionResult | None = None

    @property
    def result(self) -> CorrectionResult | None:
        return self._result

    def load(self) -> None:
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            self._text = f.read()

    def get_full_text(self) -> str:
        return self._text

    def apply_corrections(
        self, errors: list, markup: bool = False, track_changes: bool = False
    ) -> CorrectionResult:
        """Apply corrections to the text.

        Plain text has no formatting, so ``markup`` / ``track_changes`` are
        ignored — corrections are applied as clean replacements.
        """
        text = self._text
        for err in sorted(errors, key=lambda e: e.start, reverse=True):
            if 0 <= err.start <= err.end <= len(text):
                text = text[:err.start] + err.correct + text[err.end:]
        self._text = text
        self._result = CorrectionResult(
            original_text=self._text, corrected_text=text, errors=errors,
        )
        return self._result

    def replace_full_text(self, new_text: str) -> None:
        self._text = new_text

    def save(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self._text)
