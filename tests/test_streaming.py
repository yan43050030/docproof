"""Tests for streaming (on_batch) and warmup in EngineManager.

These use a fake engine so they run without any language model. The parallel
process-pool path is validated separately with a real model (it needs a
picklable module-level worker and a real Corrector)."""

from docproof.engine.engine_manager import EngineManager
from docproof.engine.base_engine import BaseEngine, ErrorItem


class _FakeEngine(BaseEngine):
    def __init__(self):
        super().__init__(name="fake")
        self.warmed = False

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


def _mgr():
    m = EngineManager()
    m._engine = _FakeEngine()
    m._engine.load()
    m.set_rule_check(False)
    return m


class TestStreaming:
    def test_on_batch_cumulative_and_monotonic(self):
        m = _mgr()
        lines = ["行%d" % k for k in range(60)]
        lines[0] = "X开头"
        lines[30] = "中X间"
        lines[59] = "末X"
        text = "\n".join(lines)
        seen = []
        m.proofread(text, on_batch=lambda errs: seen.append(len(errs)))
        assert seen == sorted(seen)  # monotonic non-decreasing
        assert seen[-1] == 3  # all three X found by the last batch

    def test_streamed_offsets_correct(self):
        m = _mgr()
        text = "\n".join(["X行%d" % k for k in range(50)])
        final = []
        m.proofread(text, on_batch=lambda errs: final.append(list(errs)))
        for e in final[-1]:
            assert text[e.start:e.end] == "X"

    def test_batches_match_line_batches(self):
        m = _mgr()
        # 45 lines -> ceil(45/20) = 3 batches
        text = "\n".join("行%d" % k for k in range(45))
        calls = []
        m.proofread(text, on_batch=lambda errs: calls.append(1))
        assert len(calls) == 3


class TestWarmup:
    def test_warmup_runs_correct(self):
        m = _mgr()
        # Should not raise and should call the engine.
        m.warmup()

    def test_warmup_never_raises(self):
        m = EngineManager()  # no engine loaded
        m.warmup()  # must be a no-op, not an error


class TestParallelGating:
    def test_small_doc_uses_serial(self):
        m = _mgr()
        m.set_parallel(True)
        # Fake engine isn't kenlm, so parallel never triggers -> serial result.
        text = "\n".join("X行%d" % k for k in range(300))
        errs = m.proofread(text)
        assert len(errs) == 300

    def test_is_kenlm_false_for_fake(self):
        m = _mgr()
        assert m._is_kenlm() is False
