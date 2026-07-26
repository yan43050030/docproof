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

        # Check the model file first — no point importing pycorrector (or letting
        # it fall back to a 2.95GB download) if the .klm file isn't present.
        import os
        model_path = self.model_path
        if not model_path or not os.path.exists(model_path):
            return False  # model not downloaded yet

        try:
            from pycorrector.corrector import Corrector
        except ImportError as e:
            missing = str(e).replace("'", "")
            raise ImportError(
                f"无法导入 pycorrector: {missing}\n\n"
                f"请确保:\n"
                f"1. third_party/pycorrector 目录存在且完整\n"
                f"2. 已安装所有依赖: pip install pypinyin loguru kenlm"
            ) from e

        self._corrector = Corrector(language_model_path=model_path)

        # Eagerly initialise the underlying detector so the language model is
        # actually opened *now*. Otherwise pycorrector lazily initialises on the
        # first correct() call and, if the model path is unusable, silently
        # falls back to downloading the 2.95GB default model — which fails
        # offline with a cryptic error. Failing here keeps the error clear and
        # prevents that fallback. We also re-assert our path afterwards.
        try:
            self._corrector.correct("初始化")
        except Exception as e:
            self._corrector = None
            hint = "文件可能损坏或不完整，请重新下载。"
            # kenlm's C++ file open can't handle non-ASCII (e.g. Chinese) paths
            # on Windows, so a program installed under a Chinese folder fails to
            # open a .klm even when it exists.
            if not model_path.isascii():
                hint = (
                    "程序所在路径含中文/非英文字符，Kenlm 引擎可能无法读取该路径下的模型。\n"
                    "解决办法：把程序整个文件夹移动到纯英文路径（如 D:\\DocProof\\）后重试；\n"
                    "或改用 MacBERT 引擎（不受路径影响）。若路径已是英文，则文件可能损坏，请重新下载。"
                )
            raise RuntimeError(
                f"语言模型无法加载：{model_path}\n{hint}\n\n原始错误: {e}"
            ) from e

        # Guard against pycorrector having swapped in its default model path.
        actual = getattr(self._corrector, "language_model_path", model_path)
        if actual != model_path:
            self._corrector = None
            raise RuntimeError(
                f"语言模型路径异常（期望 {model_path}，实际 {actual}）。"
            )

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
