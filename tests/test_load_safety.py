"""Regression tests for model-loading safety (v0.4.4 field bugs).

Bug 1: a fresh offline machine auto-loaded MacBERT (deps present but weights not
cached), which crashed with a JSON error. auto_load must only pick offline-ready
models.

Bug 2: loading a Kenlm model whose .klm file is absent must fail cleanly and must
never let pycorrector fall back to downloading its 2.95GB default model. The
None-path guard must also not raise TypeError.
"""

import docproof.config as config
from docproof.config import get_offline_model, is_model_ready_offline
from docproof.engine.kenlm_engine import KenlmEngine


class TestOfflineAutoSelect:
    def test_get_offline_model_returns_none_when_nothing_ready(self, monkeypatch):
        monkeypatch.setattr(config, "is_model_ready_offline", lambda k: False)
        assert get_offline_model() is None

    def test_offline_model_only_offline_ready(self, monkeypatch):
        # Only kenlm-base is "ready offline"; it must be chosen even though
        # macbert deps might be importable.
        monkeypatch.setattr(config, "is_model_ready_offline",
                            lambda k: k == "kenlm-base")
        assert get_offline_model() == "kenlm-base"

    def test_auto_load_uses_offline_only(self, monkeypatch):
        import docproof.engine.engine_manager as em_mod
        called = {}

        def fake_offline():
            called["offline"] = True
            return None

        monkeypatch.setattr(em_mod, "get_offline_model", fake_offline)
        mgr = em_mod.EngineManager()
        ok, msg = mgr.auto_load()
        assert called.get("offline") is True
        assert ok is False
        assert mgr.engine is None


class TestKenlmMissingModel:
    def test_none_path_returns_false_not_typeerror(self):
        class NoPathKenlm(KenlmEngine):
            @property
            def model_path(self):
                return None

        eng = NoPathKenlm(model_key="kenlm-large")
        # Must return False cleanly (previously raised TypeError on
        # os.path.exists(None)).
        assert eng.load() is False
        assert eng.loaded is False

    def test_missing_file_returns_false(self, tmp_path):
        class MissingKenlm(KenlmEngine):
            @property
            def model_path(self):
                return str(tmp_path / "does_not_exist.klm")

        eng = MissingKenlm(model_key="kenlm-base")
        assert eng.load() is False


class TestManagerMissingModel:
    def test_load_missing_kenlm_is_clean(self, monkeypatch):
        import docproof.engine.engine_manager as em_mod
        # get_model_path returns None -> _build_kenlm reports (via load) a clean error.
        monkeypatch.setattr(em_mod, "get_model_path", lambda k: None)
        mgr = em_mod.EngineManager()
        ok, msg = mgr.load("kenlm-large")
        assert ok is False
        assert "不存在" in msg
