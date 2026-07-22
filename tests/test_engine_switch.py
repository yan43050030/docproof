"""Regression test: a failed engine switch must not break the working engine.

Field bug: MacBERT loaded fine, then switching to a Kenlm model (whose .klm file
was absent) failed — but the old code unloaded the current engine *before*
trying the new one, so a failed switch left the app with no usable engine and a
stale current_key, making it impossible to switch back.
"""

import docproof.engine.engine_manager as em_mod
from docproof.engine.engine_manager import EngineManager
from docproof.engine.base_engine import BaseEngine, ErrorItem


class _FakeEngine(BaseEngine):
    def __init__(self, name):
        super().__init__(name=name)

    def load(self):
        self._loaded = True
        return True

    def unload(self):
        self._loaded = False

    def correct(self, text):
        return []


def _mgr_with_current(key="macbert"):
    mgr = EngineManager()
    eng = _FakeEngine(key)
    eng.load()
    mgr._engine = eng
    mgr._current_key = key
    return mgr, eng


class TestFailedSwitchKeepsEngine:
    def test_failed_kenlm_switch_preserves_macbert(self, monkeypatch):
        # No Kenlm file -> build fails.
        monkeypatch.setattr(em_mod, "get_model_path", lambda k: None)
        mgr, macbert = _mgr_with_current("macbert")

        ok, msg = mgr.load("kenlm-base")
        assert ok is False
        # The previously-working engine must still be loaded and current.
        assert mgr.engine is macbert
        assert macbert.loaded is True
        assert mgr.current_model_key == "macbert"
        assert mgr.is_loaded is True

    def test_successful_switch_unloads_old(self, monkeypatch):
        monkeypatch.setattr(em_mod, "get_model_path", lambda k: "/tmp/x.klm")
        import os
        monkeypatch.setattr(os.path, "exists", lambda p: True)

        new_engine = _FakeEngine("kenlm-base")

        def fake_build_kenlm(model_key):
            new_engine.load()
            return True, "ok", new_engine

        mgr, macbert = _mgr_with_current("macbert")
        monkeypatch.setattr(mgr, "_build_kenlm", fake_build_kenlm)

        ok, msg = mgr.load("kenlm-base")
        assert ok is True
        assert mgr.engine is new_engine
        assert mgr.current_model_key == "kenlm-base"
        # Old engine was unloaded.
        assert macbert.loaded is False
