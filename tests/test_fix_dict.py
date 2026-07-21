"""Tests for the forced-correction dictionary and per-rule toggles."""

import os
import tempfile

from docproof.engine.base_engine import BaseEngine, ErrorItem
from docproof.engine.engine_manager import EngineManager
from docproof.engine.rule_engine import RuleEngine
from docproof.engine.user_dict import FixDict


class _NullEngine(BaseEngine):
    def load(self):
        self._loaded = True
        return True

    def unload(self):
        pass

    def correct(self, text):
        return []


def _write_dict(content: str) -> str:
    path = tempfile.mktemp(suffix=".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestFixDict:
    def test_load_pairs(self):
        path = _write_dict("# 注释\n因该 应该\n甲 乙\n")
        try:
            fd = FixDict(path)
            assert fd.pair_count == 2
        finally:
            os.remove(path)

    def test_find_errors_all_occurrences(self):
        path = _write_dict("因该 应该\n")
        try:
            fd = FixDict(path)
            errs = fd.find_errors("因该来的。他也因该来。")
            assert len(errs) == 2
            assert all(e.category == "custom" for e in errs)
            text = "因该来的。他也因该来。"
            for e in errs:
                assert text[e.start:e.end] == "因该"
        finally:
            os.remove(path)

    def test_missing_file_is_empty(self):
        fd = FixDict("/nonexistent/fix_dict.txt")
        assert fd.pair_count == 0
        assert fd.find_errors("任何文本") == []

    def test_reload_picks_up_changes(self):
        path = _write_dict("因该 应该\n")
        try:
            fd = FixDict(path)
            assert fd.pair_count == 1
            with open(path, "a", encoding="utf-8") as f:
                f.write("甲 乙\n")
            os.utime(path, (0, 9999999999))  # force mtime change
            fd.reload()
            assert fd.pair_count == 2
        finally:
            os.remove(path)


class TestFixDictInManager:
    def test_fix_overrides_engine(self):
        path = _write_dict("因该 应该\n")
        try:
            m = EngineManager()
            m._engine = _NullEngine()
            m._engine.load()
            m.set_rule_check(False)
            m._fix_dict = FixDict(path)
            errs = m.proofread("他因该来")
            assert len(errs) == 1
            assert errs[0].correct == "应该"
            assert errs[0].category == "custom"
        finally:
            os.remove(path)


class TestRuleToggles:
    def test_disable_ascii_punct(self):
        e = RuleEngine(check_ascii_punct=False)
        assert not any(x.error == "," for x in e.correct("你好,世界"))

    def test_disable_han_space(self):
        e = RuleEngine(check_han_space=False)
        assert e.correct("中文 空格") == []

    def test_disable_repeat_punct(self):
        e = RuleEngine(check_repeat_punct=False)
        assert e.correct("结束了。。") == []

    def test_manager_set_rule_options(self):
        m = EngineManager()
        m._engine = _NullEngine()
        m._engine.load()
        m.set_rule_options(ascii_punct=False)
        assert not any(e.error == "," for e in m.proofread("你好,世界"))
        m.set_rule_options(ascii_punct=True)
        assert any(e.error == "," for e in m.proofread("你好,世界"))
