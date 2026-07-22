"""Tests for loading a pre-downloaded MacBERT model from a local folder.

Field bug: a user placed the MacBERT model locally but selecting it still failed,
because pycorrector/transformers looked up the HuggingFace repo id in its cache
layout and never saw the user's files. The fix locates a local model folder and
loads it directly.
"""

import json
import os

import docproof.config as config


def _make_macbert_dir(root: str, name: str = "macbert",
                      weight: str = "pytorch_model.bin",
                      config_content: str = '{"model_type": "bert"}') -> str:
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
        f.write(config_content)
    with open(os.path.join(d, weight), "wb") as f:
        f.write(b"\x00" * 200_000)
    with open(os.path.join(d, "vocab.txt"), "w", encoding="utf-8") as f:
        f.write("的\n")
    return d


class TestLocalMacBert:
    def test_finds_local_macbert_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        d = _make_macbert_dir(str(tmp_path))
        assert config.get_macbert_model_path() == d
        assert config.is_macbert_cached() is True

    def test_finds_safetensors_variant(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        d = _make_macbert_dir(str(tmp_path), name="macbert4csc-base-chinese",
                              weight="model.safetensors")
        assert config.get_macbert_model_path() == d

    def test_empty_config_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        _make_macbert_dir(str(tmp_path), config_content="")
        assert config.get_macbert_model_path() is None
        assert config.is_macbert_cached() is False

    def test_missing_weights_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        d = os.path.join(str(tmp_path), "macbert")
        os.makedirs(d)
        with open(os.path.join(d, "config.json"), "w") as f:
            f.write('{"model_type": "bert"}')
        assert config.get_macbert_model_path() is None

    def test_hf_cache_snapshot_detected(self, tmp_path, monkeypatch):
        # Mirror a real HuggingFace cache: macbert_cache/hub/models--*/snapshots/<hash>/
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        snap = tmp_path / "macbert_cache" / "hub" \
            / "models--shibing624--macbert4csc-base-chinese" \
            / "snapshots" / "deadbeef"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text('{"model_type": "bert"}')
        (snap / "pytorch_model.bin").write_bytes(b"\x00" * 200_000)
        (snap / "vocab.txt").write_text("的\n")
        # Noise dirs the user reported (xet, stray json) must not interfere.
        (tmp_path / "macbert_cache" / "xet").mkdir()
        (tmp_path / "macbert_cache" / ".agent_harnesses.json").write_text("{}")
        assert config.get_macbert_model_path() == str(snap)
        assert config.is_macbert_cached() is True

    def test_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        assert config.get_macbert_model_path() is None


class TestMacBertDiagnosis:
    """The Xet/pointer scenario the user hit: files present but not materialised."""

    def _snapshot(self, tmp_path):
        snap = tmp_path / "macbert_cache" / "hub" \
            / "models--shibing624--macbert4csc-base-chinese" / "snapshots" / "h1"
        snap.mkdir(parents=True)
        return snap

    def test_empty_config_is_diagnosed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        snap = self._snapshot(tmp_path)
        (snap / "config.json").write_text("")            # pointer/empty stub
        (snap / "pytorch_model.bin").write_bytes(b"\x00" * 200_000)
        assert config.get_macbert_model_path() is None   # not treated as usable
        diag = config.diagnose_macbert()
        assert diag is not None and "config.json" in diag

    def test_pointer_weight_is_diagnosed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        snap = self._snapshot(tmp_path)
        (snap / "config.json").write_text('{"model_type": "bert"}')
        (snap / "pytorch_model.bin").write_bytes(b"\x00" * 10)  # tiny pointer
        assert config.get_macbert_model_path() is None
        diag = config.diagnose_macbert()
        assert diag is not None and "权重" in diag

    def test_no_diagnosis_when_healthy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        snap = self._snapshot(tmp_path)
        (snap / "config.json").write_text('{"model_type": "bert"}')
        (snap / "pytorch_model.bin").write_bytes(b"\x00" * 200_000)
        assert config.get_macbert_model_path() == str(snap)
        assert config.diagnose_macbert() is None

    def test_engine_receives_local_path(self, tmp_path, monkeypatch):
        # engine_manager._load_macbert should build the engine with the local
        # path when one is present.
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        d = _make_macbert_dir(str(tmp_path))

        captured = {}

        class FakeEngine:
            def __init__(self, threshold=0.5, model_name_or_path=None):
                captured["path"] = model_name_or_path

            def load(self, progress_callback=None):
                return False  # don't actually load a model

        import docproof.engine.macbert_engine as me
        monkeypatch.setattr(me, "MacBertEngine", FakeEngine)

        from docproof.engine.engine_manager import EngineManager
        mgr = EngineManager()
        mgr._load_macbert("macbert")
        assert captured["path"] == d
