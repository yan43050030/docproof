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
USER_MODELS_DIR = os.path.join(os.path.expanduser("~/.docproof"), "models")
MODEL_SEARCH_DIRS = [PROJECT_MODELS_DIR, USER_MODELS_DIR]

# Make third_party/pycorrector importable
_THIRD_PARTY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "third_party", "pycorrector")
)
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


def get_model_path(model_key: str) -> str | None:
    """Find a model file across all search directories. Returns path or None."""
    filename = MODELS[model_key].get("filename")
    if filename is None:
        return None  # not a downloadable file (e.g., macbert)
    for d in MODEL_SEARCH_DIRS:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    return os.path.join(MODEL_SEARCH_DIRS[0], filename)


def is_model_available(model_key: str) -> bool:
    """Check if a model is ready to use (file exists OR deps installed for auto-download models)."""
    info = MODELS[model_key]
    if info.get("filename"):
        return is_model_downloaded(model_key)
    # For models without a downloadable file (like macbert),
    # check if required Python packages are installed
    return _check_dependencies(info.get("requires"))


def is_model_downloaded(model_key: str) -> bool:
    """Check if a model file exists in any search directory."""
    path = get_model_path(model_key)
    return path is not None and os.path.exists(path)


def any_model_downloaded() -> bool:
    """Check if any model is available."""
    return any(is_model_available(k) for k in MODELS)


def get_available_model() -> str | None:
    """Return the first available model key, or None. Prefers recommended."""
    for key in [DEFAULT_MODEL] + [k for k in MODELS if k != DEFAULT_MODEL]:
        if is_model_available(key):
            return key
    return None
