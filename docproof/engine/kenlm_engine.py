"""Kenlm statistical language model engine.

Wraps pycorrector's Corrector class, which uses:
- Kenlm n-gram language model for scoring
- Pinyin similarity + character shape similarity for candidate generation
"""

from __future__ import annotations

from docproof.config import MODELS, get_model_path
from docproof.engine.base_engine import BaseEngine, ErrorItem


class KenlmEngine(BaseEngine):
    """Proofreading engine using Kenlm statistical language model."""

    def __init__(self, model_key: str = "kenlm-base"):
        super().__init__(name=f"kenlm-{model_key}")
        self._model_key = model_key
        self._corrector = None

    @property
    def model_path(self) -> str:
        return get_model_path(self._model_key)

    @property
    def model_info(self) -> dict:
        return MODELS[self._model_key]

    def load(self) -> bool:
        """Load the Kenlm model and initialize Corrector."""
        if self._loaded:
            return True

        try:
            from pycorrector.corrector import Corrector
        except ImportError as e:
            raise ImportError(
                "无法导入 pycorrector。请确保 third_party/pycorrector 目录存在。"
            ) from e

        model_path = self.model_path
        if not __import__("os").path.exists(model_path):
            return False  # model not downloaded yet

        self._corrector = Corrector(language_model_path=model_path)
        self._loaded = True
        return True

    def unload(self) -> None:
        self._corrector = None
        self._loaded = False

    def correct(self, text: str) -> list[ErrorItem]:
        """Run proofreading on text."""
        if not self._loaded:
            raise RuntimeError("Engine not loaded. Call load() first.")

        result = self._corrector.correct(text)
        errors = []
        for error_word, correct_word, position in result.get("errors", []):
            errors.append(ErrorItem(
                error=error_word,
                correct=correct_word,
                start=position,
                end=position + len(error_word),
            ))
        return errors
