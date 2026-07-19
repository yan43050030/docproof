"""Tests for MacBERT chunking, engine-manager merge/proofread, and reports."""

from docproof.engine.macbert_engine import _split_into_chunks
from docproof.engine.engine_manager import EngineManager
from docproof.engine.base_engine import BaseEngine, ErrorItem
from docproof import report


class _FakeEngine(BaseEngine):
    """Reports every 'X' in the given text as an error X -> Y."""

    def load(self):
        self._loaded = True
        return True

    def unload(self):
        pass

    def correct(self, text):
        out = []
        i = text.find("X")
        while i != -1:
            out.append(ErrorItem("X", "Y", i, i + 1))
            i = text.find("X", i + 1)
        return out


class TestChunking:
    def test_short_line_single_chunk(self):
        assert _split_into_chunks("短句", max_len=200) == [(0, "短句")]

    def test_long_line_split(self):
        line = "。".join(["句子内容"] * 100)  # well over 200 chars
        chunks = _split_into_chunks(line, max_len=50)
        assert len(chunks) > 1
        # Reassembling by offset reproduces the original line.
        rebuilt = [""] * (len(line))
        text = list(line)
        for offset, chunk in chunks:
            assert line[offset:offset + len(chunk)] == chunk
        # No gaps: chunk offsets tile the whole line.
        total = sum(len(c) for _, c in chunks)
        assert total == len(line)

    def test_prefers_sentence_boundary(self):
        line = "第一句。" + "第二句" * 100
        chunks = _split_into_chunks(line, max_len=10)
        assert chunks[0][1].endswith("。")


class TestProofreadMerge:
    def _mgr(self):
        m = EngineManager()
        m._engine = _FakeEngine()
        m._engine.load()
        return m

    def test_batched_offsets_correct(self):
        m = self._mgr()
        m.set_rule_check(False)
        lines = ["行%d" % k for k in range(60)]
        lines[0] = "X开头"
        lines[59] = "末尾X"
        text = "\n".join(lines)
        errs = m.proofread(text)
        assert errs
        for e in errs:
            assert text[e.start:e.end] == "X"

    def test_rule_pass_merged(self):
        m = self._mgr()
        m.set_rule_check(True)
        # ASCII comma between Han -> rule engine finds it; fake engine finds none.
        errs = m.proofread("你好,世界")
        assert any(e.category == "punctuation" for e in errs)

    def test_should_stop(self):
        m = self._mgr()
        m.set_rule_check(False)
        text = "\n".join("行%d" % k for k in range(100))
        assert m.proofread(text, should_stop=lambda: True) == []

    def test_merge_skips_overlaps(self):
        primary = [ErrorItem("错字", "错别字", 5, 7)]
        extra = [ErrorItem("字", "子", 6, 7, category="punctuation")]
        merged = EngineManager._merge(primary, extra)
        assert len(merged) == 1  # overlapping extra dropped


class TestReport:
    def _errs(self):
        return [
            ErrorItem("错字", "错别字", 0, 2, category="spelling"),
            ErrorItem(",", "，", 5, 6, category="punctuation"),
        ]

    def test_text_report(self):
        r = report.build_text_report("doc.docx", self._errs())
        assert "错字" in r and "错别字" in r
        assert "疑似问题总数: 2" in r

    def test_html_report(self):
        r = report.build_html_report("doc.docx", self._errs())
        assert "<table" in r and "错别字" in r

    def test_empty_report(self):
        r = report.build_text_report("doc.docx", [])
        assert "未发现问题" in r
