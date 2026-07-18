"""Engine manager for model lifecycle."""

from __future__ import annotations

from docproof.config import MODELS, DEFAULT_MODEL, get_available_model, get_model_path
from docproof.engine.kenlm_engine import KenlmEngine


class EngineManager:
    """Manages proofreading engine loading, switching, and status."""

    def __init__(self):
        self._current_key: str | None = None
        self._engine: KenlmEngine | None = None

    @property
    def engine(self) -> KenlmEngine | None:
        return self._engine

    @property
    def is_loaded(self) -> bool:
        return self._engine is not None and self._engine.loaded

    @property
    def current_model_key(self) -> str | None:
        return self._current_key

    def auto_load(self) -> tuple[bool, str]:
        """
        Try to load the best available model.
        Returns (success, message).
        """
        available = get_available_model()
        if available is None:
            return False, "未找到任何语言模型，请先下载模型。"
        return self.load(available)

    def load(self, model_key: str) -> tuple[bool, str]:
        """Load a specific model. Returns (success, message)."""
        if model_key not in MODELS:
            return False, f"未知模型: {model_key}"

        model_path = get_model_path(model_key)
        if not __import__("os").path.exists(model_path):
            return False, f"模型文件不存在: {model_path}"

        if self._engine:
            self._engine.unload()

        engine = KenlmEngine(model_key=model_key)
        try:
            ok = engine.load()
            if ok:
                self._engine = engine
                self._current_key = model_key
                return True, f"已加载: {MODELS[model_key]['name']}"
            else:
                return False, "模型加载失败"
        except Exception as e:
            return False, f"加载出错: {e}"

    def unload(self) -> None:
        if self._engine:
            self._engine.unload()
            self._engine = None
            self._current_key = None
