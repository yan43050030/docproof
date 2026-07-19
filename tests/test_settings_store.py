"""Tests for the persistent settings store."""

import os
import tempfile

from docproof.settings_store import SettingsStore, DEFAULTS


class TestSettingsStore:
    def test_defaults_when_missing(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        s = SettingsStore(path)
        assert s.threshold == DEFAULTS["macbert_threshold"]
        assert s.rule_check_enabled is True

    def test_set_and_persist(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        s = SettingsStore(path)
        s.set("macbert_threshold", 0.7)
        s.set("rule_check_enabled", False)
        # Reload from disk.
        s2 = SettingsStore(path)
        assert s2.threshold == 0.7
        assert s2.rule_check_enabled is False

    def test_corrupt_file_falls_back(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        s = SettingsStore(path)
        assert s.threshold == 0.5

    def test_unknown_keys_ignored(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        s = SettingsStore(path)
        s.update(macbert_threshold=0.3)
        s2 = SettingsStore(path)
        assert s2.get("macbert_threshold") == 0.3

    def test_threshold_invalid_value(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        s = SettingsStore(path)
        s.set("macbert_threshold", "nope")
        assert s.threshold == 0.5
