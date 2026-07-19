"""Engine manager — supports Kenlm (CPU) and MacBERT (deep learning) engines."""

from __future__ import annotations

import os
from typing import Callable

from docproof.config import (
    MODELS,
    ENGINE_TYPES,
    get_available_model,
    get_model_path,
    _check_dependencies,
)
from docproof.engine.base_engine import BaseEngine
from docproof.engine.kenlm_engine import KenlmEngine


class EngineManager:
    """Manages proofreading engine loading, switching, and status."""

    def __init__(self):
        self._current_key: str | None = None
        self._engine: BaseEngine | None = None

    @property
    def engine(self) -> BaseEngine | None:
        return self._engine

    @property
    def is_loaded(self) -> bool:
        return self._engine is not None and self._engine.loaded

    @property
    def current_model_key(self) -> str | None:
        return self._current_key

    # ---- Public API ----

    def auto_load(self) -> tuple[bool, str]:
        """Try to load the best available model. Returns (success, message)."""
        available = get_available_model()
        if available is None:
            return False, "未找到任何语言模型，请先下载模型或安装 MacBERT 依赖。"
        return self.load(available)

    def load(self, model_key: str,
             progress_callback: Callable[[str], None] | None = None
             ) -> tuple[bool, str]:
        """Load a specific model. Returns (success, message)."""
        if model_key not in MODELS:
            return False, f"未知模型: {model_key}"

        info = MODELS[model_key]
        engine_type = info.get("engine_type", "kenlm")

        # Check dependencies first
        requires = info.get("requires", [])
        if requires and not _check_dependencies(requires):
            return False, (
                f"MacBERT 需要额外依赖:\n"
                f"  pip install torch transformers\n\n"
                f"请在终端运行上述命令后重试。\n"
                f"或使用 Kenlm 模型（无需额外依赖）。"
            )

        # Unload current engine
        if self._engine:
            self._engine.unload()

        ok = False
        msg = ""

        if engine_type == ENGINE_TYPES["kenlm"]:
            ok, msg = self._load_kenlm(model_key)
        elif engine_type == ENGINE_TYPES["macbert"]:
            ok, msg = self._load_macbert(model_key, progress_callback)
        else:
            return False, f"不支持的引擎类型: {engine_type}"

        if ok:
            self._current_key = model_key
            msg = f"已加载: {info['name']}"

        return ok, msg

    def unload(self) -> None:
        if self._engine:
            self._engine.unload()
            self._engine = None
            self._current_key = None

    # ---- Dependency check ----

    @staticmethod
    def check_macbert_ready() -> tuple[bool, str]:
        """Check if MacBERT dependencies are installed. Returns (ready, help_text)."""
        if _check_dependencies(["torch", "transformers"]):
            return True, "MacBERT 依赖已就绪，可以使用。"
        return False, (
            "MacBERT 需要安装 PyTorch 和 Transformers:\n\n"
            "  pip install torch transformers\n\n"
            "首次运行时会自动下载模型 (~400MB)。"
        )

    # ---- Internal ----

    def _load_kenlm(self, model_key: str) -> tuple[bool, str]:
        model_path = get_model_path(model_key)
        if not model_path or not os.path.exists(model_path):
            return False, (
                f"模型文件不存在。\n"
                f"请下载 .klm 文件放入 models/ 目录:\n"
                f"  {MODELS[model_key].get('url', '')}"
            )

        engine = KenlmEngine(model_key=model_key)
        try:
            if engine.load():
                self._engine = engine
                return True, "ok"
            return False, "模型加载失败"
        except Exception as e:
            return False, f"加载出错: {e}"

    def _load_macbert(self, model_key: str,
                      progress_callback=None) -> tuple[bool, str]:
        try:
            from docproof.engine.macbert_engine import MacBertEngine
        except ImportError as e:
            return False, f"导入 MacBERT 引擎失败: {e}"

        engine = MacBertEngine()
        try:
            if engine.load(progress_callback=progress_callback):
                self._engine = engine
                return True, "ok"
            return False, "MacBERT 模型加载失败"
        except Exception as e:
            return False, f"加载出错: {e}"
