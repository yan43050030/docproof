"""MacBERT deep learning engine.

Uses shibing624/macbert4csc-base-chinese — a MacBERT variant fine-tuned
for Chinese Spelling Correction. Requires torch + transformers.

Model (~400MB) auto-downloads from HuggingFace on first use.
F1 score: 0.83 on SIGHAN-2015 (vs Kenlm's ~0.31).
"""

from __future__ import annotations

import sys
from typing import Callable

from docproof.engine.base_engine import BaseEngine, ErrorItem


class MacBertEngine(BaseEngine):
    """Proofreading engine using MacBERT4CSC deep learning model."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="macbert")
        self._threshold = threshold
        self._corrector = None

    def load(self, progress_callback: Callable[[str], None] | None = None) -> bool:
        """Load the MacBERT model from HuggingFace (auto-downloads ~400MB on first run)."""
        if self._loaded:
            return True

        try:
            from pycorrector.macbert.macbert_corrector import MacBertCorrector
        except ImportError as e:
            raise ImportError(
                "MacBERT 引擎需要 PyTorch 和 Transformers。\n"
                "请运行: pip install torch transformers\n"
                "或下载完整版便携包。"
            ) from e

        if progress_callback:
            progress_callback("正在加载 MacBERT 模型（首次使用需下载 ~400MB）...")

        self._corrector = MacBertCorrector()
        self._loaded = True

        if progress_callback:
            progress_callback("MacBERT 模型加载完成")

        return True

    def unload(self) -> None:
        self._corrector = None
        self._loaded = False

    def correct(self, text: str) -> list[ErrorItem]:
        """Run MacBERT proofreading on text.

        Splits by newlines before correction to avoid a known issue
        where MacBERT's tokenizer struggles with multi-line input.
        """
        if not self._loaded:
            raise RuntimeError("Engine not loaded. Call load() first.")

        lines = text.split("\n")
        all_errors = []
        offset = 0

        for line in lines:
            if not line.strip():
                offset += len(line) + 1  # +1 for the \n
                continue

            result = self._corrector.correct(line, threshold=self._threshold)

            for error_word, correct_word, position in result.get("errors", []):
                all_errors.append(ErrorItem(
                    error=error_word,
                    correct=correct_word,
                    start=offset + position,
                    end=offset + position + len(error_word),
                ))
            offset += len(line) + 1  # +1 for the \n

        return all_errors
