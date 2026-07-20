"""Tests for docproof.config module.

These test the pure-logic config functions without side effects.
"""

import os
import tempfile

from docproof.config import (
    MODELS,
    MODEL_PRIORITY,
    ENGINE_TYPES,
    get_model_path,
    is_model_available,
    is_model_downloaded,
    is_model_ready_offline,
    is_macbert_cached,
    any_model_downloaded,
    get_available_model,
    _check_dependencies,
)


class TestModelRegistry:
    """Tests for model registry structure."""

    def test_all_models_have_required_fields(self):
        required = {"name", "description", "engine_type"}
        for key, info in MODELS.items():
            for field in required:
                assert field in info, f"Model '{key}' missing field '{field}'"

    def test_all_model_engine_types_valid(self):
        for key, info in MODELS.items():
            assert info["engine_type"] in ENGINE_TYPES.values(), (
                f"Model '{key}' has unknown engine_type: {info['engine_type']}"
            )

    def test_macbert_is_recommended(self):
        assert MODELS["macbert"]["recommended"] is True

    def test_kenlm_models_have_filename(self):
        for key in ["kenlm-tiny", "kenlm-base", "kenlm-large"]:
            assert MODELS[key]["filename"] is not None

    def test_macbert_has_no_filename(self):
        assert MODELS["macbert"]["filename"] is None

    def test_model_priority_contains_all_kenlm(self):
        for key in ["macbert", "kenlm-large", "kenlm-base", "kenlm-tiny"]:
            assert key in MODEL_PRIORITY


class TestDependencyCheck:
    """Tests for _check_dependencies."""

    def test_no_deps_always_true(self):
        assert _check_dependencies(None) is True
        assert _check_dependencies([]) is True

    def test_builtin_modules_found(self):
        assert _check_dependencies(["os", "sys", "json"]) is True

    def test_nonexistent_module_fails(self):
        assert _check_dependencies(["nonexistent_module_xyz"]) is False


class TestModelAvailability:
    """Tests for model availability checks."""

    def test_is_model_available_no_file_with_deps(self):
        # MacBERT has no filename, so availability depends on deps being installed
        # In test environment, torch/transformers may or may not be present
        result = is_model_available("macbert")
        assert isinstance(result, bool)

    def test_any_model_downloaded_returns_bool(self):
        result = any_model_downloaded()
        assert isinstance(result, bool)

    def test_get_available_model_returns_key_or_none(self):
        result = get_available_model()
        assert result is None or result in MODELS

    def test_is_model_downloaded_returns_bool(self):
        for key in MODELS:
            result = is_model_downloaded(key)
            assert isinstance(result, bool)


class TestGetModelPath:
    """Tests for get_model_path."""

    def test_returns_path_for_kenlm_model(self):
        path = get_model_path("kenlm-base")
        # If model file exists, verify it's the right one;
        # in CI without model files, None is correct (no false paths).
        if path is not None:
            assert path.endswith("people2014corpus_chars.klm")

    def test_returns_none_for_macbert(self):
        path = get_model_path("macbert")
        assert path is None


class TestOfflineReadiness:
    """Tests for offline-aware availability."""

    def test_is_macbert_cached_returns_bool(self):
        assert isinstance(is_macbert_cached(), bool)

    def test_is_model_ready_offline_returns_bool(self):
        for key in MODELS:
            assert isinstance(is_model_ready_offline(key), bool)

    def test_macbert_offline_requires_cache(self):
        # MacBERT is only offline-ready when its weights are cached, even if
        # torch/transformers happen to be installed.
        ready = is_model_ready_offline("macbert")
        if ready:
            assert is_macbert_cached()

    def test_kenlm_offline_equals_downloaded(self):
        for key in ["kenlm-tiny", "kenlm-base", "kenlm-large"]:
            assert is_model_ready_offline(key) == is_model_downloaded(key)
