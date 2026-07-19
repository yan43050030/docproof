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

# MacBERT is built on BERT, which caps input at 512 tokens. Chinese characters
# roughly map 1:1 to tokens, so we split long lines into chunks well under the
# limit at sentence-ending punctuation to avoid silently truncating input.
_MAX_CHUNK = 200
_SENTENCE_ENDS = "。！？…；\n"


def _split_into_chunks(line: str, max_len: int = _MAX_CHUNK) -> list[tuple[int, str]]:
    """Split ``line`` into (offset, chunk) pieces no longer than ``max_len``.

    Splits preferentially after sentence-ending punctuation so corrections keep
    their context; falls back to a hard cut when a single sentence is too long.
    """
    if len(line) <= max_len:
        return [(0, line)]

    chunks: list[tuple[int, str]] = []
    start = 0
    n = len(line)
    while start < n:
        end = min(start + max_len, n)
        if end < n:
            # Try to break at the last sentence end within the window.
            split = -1
            for i in range(end - 1, start, -1):
                if line[i] in _SENTENCE_ENDS:
                    split = i + 1
                    break
            if split > start:
                end = split
        chunks.append((start, line[start:end]))
        start = end
    return chunks


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
            if line.strip():
                # Long lines are chunked to stay under BERT's 512-token limit.
                for chunk_offset, chunk in _split_into_chunks(line):
                    if not chunk.strip():
                        continue
                    result = self._corrector.correct(chunk, threshold=self._threshold)
                    base = offset + chunk_offset
                    for error_word, correct_word, position in result.get("errors", []):
                        all_errors.append(ErrorItem(
                            error=error_word,
                            correct=correct_word,
                            start=base + position,
                            end=base + position + len(error_word),
                            category="spelling",
                            source="macbert",
                        ))
            offset += len(line) + 1  # +1 for the \n

        return all_errors
