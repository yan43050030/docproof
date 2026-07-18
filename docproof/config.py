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

MODELS = {
    "kenlm-tiny": {
        "name": "Kenlm 小模型 (20MB)",
        "description": "人民日报语料训练，适合快速体验，准确度一般",
        "filename": "people_chars_lm.klm",
        "url": "https://github.com/shibing624/pycorrector/releases/download/0.4.3/people_chars_lm.klm",
        "size_mb": 20,
        "recommended": False,
    },
    "kenlm-base": {
        "name": "Kenlm 标准模型 (148MB)",
        "description": "人民日报语料训练，速度与准确度均衡，推荐日常使用",
        "filename": "people2014_corpus_chars.klm",
        "url": "https://github.com/shibing624/pycorrector/releases/download/1.0.0/people2014_corpus_chars.klm",
        "size_mb": 148,
        "recommended": True,
    },
    "kenlm-large": {
        "name": "Kenlm 大模型 (2.95GB)",
        "description": "大规模语料训练，准确度最高，但下载时间长，内存占用大",
        "filename": "zh_giga.no_cna_cmn.prune01244.klm",
        "url": "https://deepspeech.bj.bcebos.com/zh_lm/zh_giga.no_cna_cmn.prune01244.klm",
        "size_mb": 2950,
        "recommended": False,
    },
}

DEFAULT_MODEL = "kenlm-base"


def get_model_path(model_key: str) -> str | None:
    """Find a model file across all search directories. Returns path or None."""
    filename = MODELS[model_key]["filename"]
    for d in MODEL_SEARCH_DIRS:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    # Not found — return the primary (project-local) path as suggestion
    return os.path.join(MODEL_SEARCH_DIRS[0], filename)


def is_model_downloaded(model_key: str) -> bool:
    """Check if a model file exists in any search directory."""
    path = get_model_path(model_key)
    return path is not None and os.path.exists(path)


def any_model_downloaded() -> bool:
    """Check if any model is available."""
    return any(is_model_downloaded(k) for k in MODELS)


def get_available_model() -> str | None:
    """Return the first available model key, or None."""
    # Prefer recommended model
    for key in [DEFAULT_MODEL] + [k for k in MODELS if k != DEFAULT_MODEL]:
        if is_model_downloaded(key):
            return key
    return None
