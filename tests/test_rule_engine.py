"""Tests for the rule-based punctuation/normalization engine."""

from docproof.engine.rule_engine import RuleEngine


def _pairs(text):
    return [(e.error, e.correct) for e in RuleEngine().correct(text)]


class TestRuleEngine:
    def test_ascii_punct_between_han(self):
        pairs = _pairs("他说:你好,世界")
        assert (":", "：") in pairs
        assert (",", "，") in pairs

    def test_digits_period_untouched(self):
        assert _pairs("版本 1.5 更新") == []

    def test_english_untouched(self):
        assert _pairs("see file.txt now") == []

    def test_space_between_han(self):
        pairs = _pairs("中文 空格")
        assert (" ", "") in pairs

    def test_repeated_punct_collapsed(self):
        pairs = _pairs("结束了。。")
        assert ("。。", "。") in pairs

    def test_emphasis_not_flagged(self):
        # ！ repetition is common emphasis and must not be flagged.
        assert _pairs("太好了！！") == []

    def test_category_is_punctuation(self):
        errs = RuleEngine().correct("他说:你好")
        assert errs and all(e.category == "punctuation" for e in errs)

    def test_offsets_are_correct(self):
        text = "他说:你好"
        for e in RuleEngine().correct(text):
            assert text[e.start:e.end] == e.error
