"""Configuration and constants for DocProof."""

import os
import sys

# ---- Paths ----

APP_NAME = "DocProof"

# Project root (where setup.py/pyproject.toml lives)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Model search paths (checked in order, first found wins)
# 1. Project-local models/ — portable, copy with the app
# 2. User data dir — traditional per-user location
PROJECT_MODELS_DIR = os.path.join(_PROJECT_ROOT, "models")
USER_DATA_DIR = os.path.expanduser("~/.docproof")
USER_MODELS_DIR = os.path.join(USER_DATA_DIR, "models")
MODEL_SEARCH_DIRS = [PROJECT_MODELS_DIR, USER_MODELS_DIR]

# Persisted user settings live in the user data dir.
SETTINGS_PATH = os.path.join(USER_DATA_DIR, "settings.json")

# MacBERT HuggingFace cache path
_MACBERT_CACHE = os.path.join(PROJECT_MODELS_DIR, "macbert_cache")

# Third-party pycorrector path
_THIRD_PARTY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "third_party", "pycorrector")
)


def init_config() -> None:
    """Initialize runtime configuration (directories, env vars, paths).

    Must be called once at startup before any engine loading.
    Safe to call multiple times (idempotent).
    """
    os.makedirs(_MACBERT_CACHE, exist_ok=True)
    os.makedirs(PROJECT_MODELS_DIR, exist_ok=True)
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = _MACBERT_CACHE
    if "TRANSFORMERS_CACHE" not in os.environ:
        os.environ["TRANSFORMERS_CACHE"] = _MACBERT_CACHE
    if "PYCORRECTOR_DATA_DIR" not in os.environ:
        os.environ["PYCORRECTOR_DATA_DIR"] = PROJECT_MODELS_DIR

    if os.path.isdir(_THIRD_PARTY) and _THIRD_PARTY not in sys.path:
        sys.path.insert(0, _THIRD_PARTY)

# ---- Model registry ----

ENGINE_TYPES = {
    "kenlm": "kenlm",
    "macbert": "macbert",
}

MODELS = {
    # ---- Kenlm 统计模型 (轻量，CPU 友好) ----
    "kenlm-tiny": {
        "name": "Kenlm 小模型 (20MB)",
        "description": "统计模型，快速体验，准确度一般",
        "filename": "people_chars_lm.klm",
        "url": "https://github.com/shibing624/pycorrector/releases/download/0.4.3/people_chars_lm.klm",
        "size_mb": 20,
        "engine_type": "kenlm",
        "recommended": False,
    },
    "kenlm-base": {
        "name": "Kenlm 标准模型 (141MB)",
        "description": "统计模型，速度与准确度均衡",
        "filename": "people2014corpus_chars.klm",
        "url": "https://github.com/shibing624/pycorrector/releases/download/1.0.0/people2014corpus_chars.klm",
        "size_mb": 141,
        "engine_type": "kenlm",
        "recommended": False,
    },
    "kenlm-large": {
        "name": "Kenlm 大模型 (2.95GB)",
        "description": "统计模型，准确度最高但体积大",
        "filename": "zh_giga.no_cna_cmn.prune01244.klm",
        "url": "https://deepspeech.bj.bcebos.com/zh_lm/zh_giga.no_cna_cmn.prune01244.klm",
        "size_mb": 2950,
        "engine_type": "kenlm",
        "recommended": False,
    },
    # ---- MacBERT 深度学习模型 (需 torch) ----
    "macbert": {
        "name": "MacBERT 深度学习模型 (~400MB)",
        "description": "BERT 纠错模型，F1=0.83，准确度远超统计模型，首次使用自动下载",
        "filename": None,  # auto-downloaded by HuggingFace transformers
        "url": "https://huggingface.co/shibing624/macbert4csc-base-chinese",
        "size_mb": 400,
        "engine_type": "macbert",
        "recommended": True,
        "requires": ["torch", "transformers"],
    },
}

DEFAULT_MODEL = "macbert"  # prefer MacBERT if available

# Priority order: best engine first, fall back to simpler ones
MODEL_PRIORITY = [
    "macbert",
    "kenlm-large",
    "kenlm-base",
    "kenlm-tiny",
]


def _check_dependencies(requires: list[str] | None) -> bool:
    """Check if required Python packages are installed."""
    if not requires:
        return True
    for pkg in requires:
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def _find_file_recursive(filename: str, search_dir: str) -> str | None:
    """Recursively search for a file by name under a directory. Returns path or None."""
    if not os.path.isdir(search_dir):
        return None
    for root, _dirs, files in os.walk(search_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def get_model_path(model_key: str) -> str | None:
    """Find a model file across all search directories (recursively). Returns path or None."""
    filename = MODELS[model_key].get("filename")
    if filename is None:
        return None  # not a downloadable file (e.g., macbert)
    for d in MODEL_SEARCH_DIRS:
        path = _find_file_recursive(filename, d)
        if path is not None:
            return path
    return None


def is_macbert_cached() -> bool:
    """Check whether MacBERT weights are already downloaded locally.

    Used to distinguish "dependencies installed" from "usable fully offline".
    Recursively scans the entire models directory tree for weight files,
    so users can place model files anywhere under models/.
    """
    for search_dir in MODEL_SEARCH_DIRS:
        if not os.path.isdir(search_dir):
            continue
        for root, _dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith((".bin", ".safetensors")):
                    return True
    return False


def is_model_available(model_key: str) -> bool:
    """Check if a model is ready to use (file exists OR deps installed for auto-download models)."""
    info = MODELS[model_key]
    if info.get("filename"):
        return is_model_downloaded(model_key)
    # For models without a downloadable file (like macbert),
    # check if required Python packages are installed
    return _check_dependencies(info.get("requires"))


def is_model_ready_offline(model_key: str) -> bool:
    """Check if a model can run without any network access right now."""
    info = MODELS[model_key]
    if info.get("filename"):
        return is_model_downloaded(model_key)
    if info.get("engine_type") == "macbert":
        return _check_dependencies(info.get("requires")) and is_macbert_cached()
    return _check_dependencies(info.get("requires"))


def is_model_downloaded(model_key: str) -> bool:
    """Check if a model file exists in any search directory."""
    path = get_model_path(model_key)
    return path is not None and os.path.exists(path)


def any_model_downloaded() -> bool:
    """Check if any model is available."""
    return any(is_model_available(k) for k in MODELS)


def _priority_keys() -> list[str]:
    return MODEL_PRIORITY + [k for k in MODELS if k not in MODEL_PRIORITY]


def get_available_model() -> str | None:
    """Return the best usable model key, or None.

    Prefers models that are ready to run fully offline (weights already present)
    so a freshly installed, network-less machine picks a downloaded Kenlm model
    instead of a MacBERT that still needs to fetch ~400MB. Falls back to any
    model whose dependencies are installed.
    """
    for key in _priority_keys():
        if is_model_ready_offline(key):
            return key
    for key in _priority_keys():
        if is_model_available(key):
            return key
    return None
