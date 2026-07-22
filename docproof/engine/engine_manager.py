"""Engine manager — supports Kenlm (CPU) and MacBERT (deep learning) engines."""

from __future__ import annotations

import os
from typing import Callable

from docproof.config import (
    MODELS,
    ENGINE_TYPES,
    get_available_model,
    get_offline_model,
    get_model_path,
    check_macbert_fully_available,
)
from docproof.engine.base_engine import BaseEngine, ErrorItem
from docproof.engine.kenlm_engine import KenlmEngine
from docproof.engine.rule_engine import RuleEngine
from docproof.engine.user_dict import FixDict


class EngineManager:
    """Manages proofreading engine loading, switching, and status."""

    def __init__(self):
        self._current_key: str | None = None
        self._engine: BaseEngine | None = None
        self._threshold: float = 0.5
        self._rule_engine = RuleEngine()
        self._rule_check_enabled: bool = True
        self._fix_dict = FixDict()
        self._parallel_enabled: bool = True

    # ---- configuration ----

    def set_threshold(self, value: float) -> None:
        self._threshold = value
        # Apply live to a loaded MacBERT engine if it exposes a threshold.
        if self._engine is not None and hasattr(self._engine, "_threshold"):
            self._engine._threshold = value

    def set_rule_check(self, enabled: bool) -> None:
        self._rule_check_enabled = enabled

    def set_rule_options(self, *, ascii_punct: bool | None = None,
                         han_space: bool | None = None,
                         repeat_punct: bool | None = None) -> None:
        """Toggle individual rule checks."""
        if ascii_punct is not None:
            self._rule_engine.check_ascii_punct = ascii_punct
        if han_space is not None:
            self._rule_engine.check_han_space = han_space
        if repeat_punct is not None:
            self._rule_engine.check_repeat_punct = repeat_punct

    @property
    def rule_check_enabled(self) -> bool:
        return self._rule_check_enabled

    @property
    def fix_dict(self) -> FixDict:
        return self._fix_dict

    def warmup(self) -> None:
        """Run a tiny correction to trigger lazy initialisation (jieba dict,
        model graph) so the user's first real run isn't slow. Safe to call in a
        background thread; never raises."""
        try:
            if self._engine is not None:
                self._engine.correct("预热。")
        except Exception:
            pass

    # Documents with at least this many lines may use the process pool. Kept
    # high because each worker reloads the language model on startup, so small
    # and medium documents are faster served serially.
    _PARALLEL_MIN_LINES = 200
    _BATCH = 20

    def set_parallel(self, enabled: bool) -> None:
        self._parallel_enabled = enabled

    def proofread(self, text: str, progress=None, should_stop=None,
                  on_batch=None) -> list[ErrorItem]:
        """Run the active engine plus the optional rule pass and merge results.

        Args:
            text: full document text (paragraphs joined by "\\n").
            progress: optional callback ``progress(done_lines, total_lines)`` for
                a real progress bar — text is processed in line batches.
            should_stop: optional callable returning True to abort early.
            on_batch: optional callback ``on_batch(cumulative_spelling_errors)``
                invoked after each batch, enabling streaming/incremental display.
        """
        if self._engine is None:
            raise RuntimeError("校对引擎未加载")

        errors = self._detect_spelling(text, progress, should_stop, on_batch)
        if should_stop is not None and should_stop():
            return []

        if self._rule_check_enabled:
            errors = self._merge(errors, self._rule_engine.correct(text))

        # Forced corrections from the user's fix dictionary win over everything.
        self._fix_dict.reload()
        fix_errors = self._fix_dict.find_errors(text)
        if fix_errors:
            fix_spans = [(e.start, e.end) for e in fix_errors]
            errors = [
                e for e in errors
                if not any(e.start < fe and e.end > fs for fs, fe in fix_spans)
            ]
            errors.extend(fix_errors)

        errors.sort(key=lambda e: e.start)
        return errors

    # ---- spelling detection (serial / parallel) ----

    def _build_chunks(self, text: str) -> list[tuple[int, str]]:
        """Split text into (base_offset, batch_text) chunks of _BATCH lines."""
        lines = text.split("\n")
        chunks = []
        base = 0
        for i in range(0, len(lines), self._BATCH):
            batch_text = "\n".join(lines[i:i + self._BATCH])
            chunks.append((base, batch_text))
            base += len(batch_text) + 1  # +1 for the joining newline
        return chunks

    def _is_kenlm(self) -> bool:
        return (self._current_key is not None
                and MODELS.get(self._current_key, {}).get("engine_type") == "kenlm")

    def _detect_spelling(self, text, progress, should_stop, on_batch
                         ) -> list[ErrorItem]:
        chunks = self._build_chunks(text)
        total = len(text.split("\n"))

        if (self._parallel_enabled and self._is_kenlm()
                and total >= self._PARALLEL_MIN_LINES
                and getattr(self._engine, "model_path", None)):
            try:
                return self._detect_parallel(chunks, total, progress,
                                             should_stop, on_batch)
            except Exception:
                pass  # any failure -> fall back to serial below

        return self._detect_serial(chunks, total, progress, should_stop, on_batch)

    def _detect_serial(self, chunks, total, progress, should_stop, on_batch
                       ) -> list[ErrorItem]:
        errors: list[ErrorItem] = []
        done = 0
        for base, batch_text in chunks:
            if should_stop is not None and should_stop():
                return errors
            for e in self._engine.correct(batch_text):
                e.start += base
                e.end += base
                errors.append(e)
            done = min(done + self._BATCH, total)
            if progress is not None:
                progress(done, total)
            if on_batch is not None:
                on_batch(list(errors))
        return errors

    def _detect_parallel(self, chunks, total, progress, should_stop, on_batch
                         ) -> list[ErrorItem]:
        from concurrent.futures import ProcessPoolExecutor
        from docproof.engine.parallel import _proofread_chunk, default_worker_count

        model_path = self._engine.model_path
        args = [(model_path, base, bt) for base, bt in chunks]
        errors: list[ErrorItem] = []
        done = 0
        with ProcessPoolExecutor(max_workers=default_worker_count()) as ex:
            # map preserves input order, so offsets and streaming stay correct.
            for chunk_result in ex.map(_proofread_chunk, args):
                if should_stop is not None and should_stop():
                    break
                for err, corr, pos in chunk_result:
                    errors.append(ErrorItem(err, corr, pos, pos + len(err),
                                            category="spelling", source="kenlm"))
                done = min(done + self._BATCH, total)
                if progress is not None:
                    progress(done, total)
                if on_batch is not None:
                    on_batch(list(errors))
        return errors

    @staticmethod
    def _merge(primary: list[ErrorItem], extra: list[ErrorItem]) -> list[ErrorItem]:
        """Append ``extra`` errors that don't overlap any ``primary`` span."""
        spans = [(e.start, e.end) for e in primary]
        merged = list(primary)
        for e in extra:
            if any(e.start < pe and e.end > ps for ps, pe in spans):
                continue
            merged.append(e)
        return merged

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
        """Silently load the best model that can run offline right now.

        Only offline-ready models are auto-loaded — we never trigger a network
        download on startup (that fails on offline/blocked machines and, for
        MacBERT, crashes with a JSON error on a partial cache). If nothing is
        ready, the app starts without an engine and the user picks one in
        Settings, which is where any download is initiated explicitly.
        """
        available = get_offline_model()
        if available is None:
            return False, "未找到可离线使用的语言模型，请在设置中选择并下载模型。"
        return self.load(available)

    def load(self, model_key: str,
             progress_callback: Callable[[str], None] | None = None
             ) -> tuple[bool, str]:
        """Load a specific model. Returns (success, message)."""
        if model_key not in MODELS:
            return False, f"未知模型: {model_key}"

        info = MODELS[model_key]
        engine_type = info.get("engine_type", "kenlm")

        # Check dependencies first (use deep import check for macbert)
        if engine_type == ENGINE_TYPES["macbert"]:
            deps_ok, detail = check_macbert_fully_available()
            if not deps_ok:
                return False, (
                    f"MacBERT 无法加载: {detail}\n\n"
                    f"请安装所需依赖后重试:\n"
                    f"  pip install torch transformers loguru tqdm pypinyin\n\n"
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
        """Check if MacBERT can actually be loaded. Returns (ready, help_text)."""
        return check_macbert_fully_available()

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

        engine = MacBertEngine(threshold=self._threshold)
        try:
            if engine.load(progress_callback=progress_callback):
                self._engine = engine
                return True, "ok"
            return False, "MacBERT 模型加载失败"
        except Exception as e:
            return False, f"加载出错: {e}"
