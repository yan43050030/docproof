"""User dictionary for whitelisting words the proofreader should skip."""

from __future__ import annotations

import os
import threading
from pathlib import Path


class UserDict:
    """Manages a user-defined whitelist of words to skip during proofreading.

    Reads from and writes to models/user_dict.txt (one word/phrase per line).
    Thread-safe for concurrent reads during proofreading.
    """

    def __init__(self, dict_path: str | None = None):
        if dict_path is None:
            from docproof.config import PROJECT_MODELS_DIR
            dict_path = os.path.join(PROJECT_MODELS_DIR, "user_dict.txt")
        self._dict_path = dict_path
        self._words: set[str] = set()
        self._lock = threading.RLock()
        self._load()

    @property
    def dict_path(self) -> str:
        return self._dict_path

    @property
    def word_count(self) -> int:
        with self._lock:
            return len(self._words)

    def _load(self) -> None:
        """Load words from the dictionary file."""
        if not os.path.exists(self._dict_path):
            return
        with self._lock:
            try:
                with open(self._dict_path, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            self._words.add(word)
            except OSError:
                pass

    def contains(self, word: str) -> bool:
        """Check if a word is in the whitelist."""
        with self._lock:
            return word in self._words

    def add_word(self, word: str) -> bool:
        """Add a word to the dictionary. Returns True if newly added."""
        word = word.strip()
        if not word:
            return False
        with self._lock:
            if word in self._words:
                return False
            self._words.add(word)
        self._save()
        return True

    def remove_word(self, word: str) -> bool:
        """Remove a word from the dictionary. Returns True if it existed."""
        with self._lock:
            if word not in self._words:
                return False
            self._words.remove(word)
        self._save()
        return True

    def reload(self) -> None:
        """Reload from disk."""
        with self._lock:
            self._words.clear()
        self._load()

    def _save(self) -> None:
        """Save words to the dictionary file."""
        os.makedirs(os.path.dirname(self._dict_path), exist_ok=True)
        with self._lock:
            try:
                with open(self._dict_path, "w", encoding="utf-8") as f:
                    f.write("# DocProof 用户词典 — 每行一个词/短语，校对时将跳过这些词\n")
                    f.write("# 以 # 开头的行为注释\n")
                    for word in sorted(self._words):
                        f.write(word + "\n")
            except OSError:
                pass

    def filter_errors(self, errors: list) -> list:
        """Filter out errors whose error text is in the user dictionary."""
        return [e for e in errors if not self.contains(e.error)]


class FixDict:
    """User-defined forced corrections: "wrong-word -> right-word" pairs.

    Stored in models/fix_dict.txt, one pair per line separated by whitespace
    (e.g. "因该 应该"). During proofreading every occurrence of a wrong word is
    reported as a "custom" correction, overriding any overlapping engine
    suggestion — the user's own mapping always wins.
    """

    def __init__(self, dict_path: str | None = None):
        if dict_path is None:
            from docproof.config import PROJECT_MODELS_DIR
            dict_path = os.path.join(PROJECT_MODELS_DIR, "fix_dict.txt")
        self._dict_path = dict_path
        self._pairs: dict[str, str] = {}
        self._mtime: float | None = None
        self._lock = threading.RLock()
        self.reload()

    @property
    def dict_path(self) -> str:
        return self._dict_path

    @property
    def pair_count(self) -> int:
        with self._lock:
            return len(self._pairs)

    def reload(self) -> None:
        """(Re)load pairs from disk if the file changed since last load."""
        try:
            mtime = os.path.getmtime(self._dict_path)
        except OSError:
            with self._lock:
                self._pairs = {}
                self._mtime = None
            return
        with self._lock:
            if mtime == self._mtime:
                return
            pairs: dict[str, str] = {}
            try:
                with open(self._dict_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split(None, 1)
                        if len(parts) == 2 and parts[0] != parts[1]:
                            pairs[parts[0]] = parts[1]
            except OSError:
                return
            self._pairs = pairs
            self._mtime = mtime

    def ensure_file(self) -> None:
        """Create the dict file with a usage header if it doesn't exist."""
        if os.path.exists(self._dict_path):
            return
        try:
            os.makedirs(os.path.dirname(self._dict_path), exist_ok=True)
            with open(self._dict_path, "w", encoding="utf-8") as f:
                f.write("# DocProof 强制纠正词典 — 每行一对：错词 正词\n")
                f.write("# 例如：\n")
                f.write("#   因该 应该\n")
                f.write("# 校对时将无条件把左边的词报为错误并建议改为右边的词，\n")
                f.write("# 且优先于引擎自己的建议。以 # 开头的行为注释。\n")
        except OSError:
            pass

    def find_errors(self, text: str) -> list:
        """Scan text and return forced-correction ErrorItems."""
        from docproof.engine.base_engine import ErrorItem
        with self._lock:
            pairs = dict(self._pairs)
        errors = []
        for wrong, right in pairs.items():
            start = text.find(wrong)
            while start != -1:
                errors.append(ErrorItem(
                    error=wrong, correct=right,
                    start=start, end=start + len(wrong),
                    category="custom", source="fix_dict",
                ))
                start = text.find(wrong, start + len(wrong))
        return errors
