"""Persistent user settings stored as JSON in the user data directory.

Keeps things the user tweaks between sessions: last-used model, MacBERT
sensitivity threshold, whether the punctuation rule pass is enabled, and the
main-window geometry. All access is defensive — a missing or corrupt file just
falls back to defaults.
"""

from __future__ import annotations

import json
import os
import threading

from docproof.config import SETTINGS_PATH

DEFAULTS: dict = {
    "last_model": None,
    "macbert_threshold": 0.5,
    "rule_check_enabled": True,
    "rule_ascii_punct": True,   # 半角标点检查
    "rule_han_space": True,     # 汉字间空格检查
    "rule_repeat_punct": True,  # 重复标点检查
    "parallel_enabled": False,  # 多核并行（仅超大文档受益；进程启动需重载模型）
    "theme": "light",           # system | light | dark
    "window_geometry": None,  # base64 QByteArray hex, optional
}


class SettingsStore:
    """Thread-safe JSON-backed settings with sensible defaults."""

    def __init__(self, path: str | None = None):
        self._path = path or SETTINGS_PATH
        self._lock = threading.RLock()
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                with self._lock:
                    self._data.update({k: v for k, v in data.items() if k in DEFAULTS})
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = value
        self._save()

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)
        self._save()

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with self._lock:
                snapshot = dict(self._data)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @property
    def threshold(self) -> float:
        try:
            return float(self.get("macbert_threshold", 0.5))
        except (TypeError, ValueError):
            return 0.5

    @property
    def rule_check_enabled(self) -> bool:
        return bool(self.get("rule_check_enabled", True))
