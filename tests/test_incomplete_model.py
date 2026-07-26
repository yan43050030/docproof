"""Tests for incomplete-download detection and copyable error dialogs."""

import os
import docproof.config as config


class TestSizeStatus:
    def test_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        assert config.kenlm_model_size_status("kenlm-base")[0] == "missing"

    def test_incomplete(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        # kenlm-large expects ~2950MB; a tiny file is incomplete.
        (tmp_path / "zh_giga.no_cna_cmn.prune01244.klm").write_bytes(b"\x00" * 4096)
        status, actual, expected = config.kenlm_model_size_status("kenlm-large")
        assert status == "incomplete" and expected == 2950

    def test_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SEARCH_DIRS", [str(tmp_path)])
        # Fake a "complete" small model by using kenlm-tiny (20MB) with >=18MB.
        (tmp_path / "people_chars_lm.klm").write_bytes(b"\x00" * (19 * 1024 * 1024))
        assert config.kenlm_model_size_status("kenlm-tiny")[0] == "ok"
