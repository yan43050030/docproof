"""Configuration and constants for DocProof."""

import os
import sys

# ---- Paths ----

APP_NAME = "DocProof"

# When running as a PyInstaller bundle, sys._MEIPASS points to the _internal/
# directory where all bundled files (including --add-data) are extracted.
# Source runs resolve everything relative to __file__.
if getattr(sys, "frozen", False):
    _BASE_DIR: str = sys._MEIPASS
    # In a PyInstaller onedir build the bundled models live under _internal/
    # (sys._MEIPASS), but users naturally drop model files next to the .exe.
    # Search both, preferring the folder beside the executable.
    _EXE_DIR: str = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _EXE_DIR = _BASE_DIR

# Model search paths (checked in order, first found wins)
# 1. models/ next to the executable — where users copy files (frozen builds)
# 2. bundled models/ (under _internal in frozen builds)
# 3. User data dir — traditional per-user location
PROJECT_MODELS_DIR = os.path.join(_BASE_DIR, "models")
EXE_MODELS_DIR = os.path.join(_EXE_DIR, "models")
USER_DATA_DIR = os.path.expanduser("~/.docproof")
USER_MODELS_DIR = os.path.join(USER_DATA_DIR, "models")


def _dedup(paths: list[str]) -> list[str]:
    seen, out = set(), []
    for p in paths:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            out.append(p)
    return out


MODEL_SEARCH_DIRS = _dedup([EXE_MODELS_DIR, PROJECT_MODELS_DIR, USER_MODELS_DIR])

# Persisted user settings live in the user data dir.
SETTINGS_PATH = os.path.join(USER_DATA_DIR, "settings.json")

# MacBERT HuggingFace cache path
_MACBERT_CACHE = os.path.join(PROJECT_MODELS_DIR, "macbert_cache")

# Third-party pycorrector path.
# In source mode, pycorrector lives at third_party/pycorrector/pycorrector/,
# so we add third_party/pycorrector/ to sys.path so "import pycorrector" works.
# In PyInstaller frozen mode, --add-data extracts the pycorrector package
# directly into _internal/pycorrector/, so we add _internal/ to sys.path.
if getattr(sys, "frozen", False):
    _THIRD_PARTY = sys._MEIPASS
else:
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


def check_macbert_fully_available() -> tuple[bool, str]:
    """Check whether the MacBERT engine can actually be loaded.

    Goes beyond _check_dependencies by performing the real import that
    MacBertEngine.load() uses.  Returns (available, detail_string).
    """
    if not _check_dependencies(["torch", "transformers"]):
        return False, "缺少 PyTorch / Transformers"
    try:
        from pycorrector.macbert.macbert_corrector import MacBertCorrector  # noqa: F401
        return True, "依赖已就绪，首次使用自动下载模型"
    except ImportError as e:
        return False, f"缺少依赖: {e}".replace("'", "")


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


# Weight and config filenames that a usable local MacBERT folder must contain.
_MACBERT_WEIGHTS = ("pytorch_model.bin", "model.safetensors")
# A materialised weight file is far larger than this; anything smaller is almost
# certainly an un-materialised pointer stub (e.g. a HuggingFace Xet pointer).
_MIN_WEIGHT_BYTES = 100 * 1024


def _valid_json_file(path: str) -> bool:
    """True if ``path`` exists and contains a non-empty JSON object.

    Guards against un-materialised pointer/stub files (Xet, LFS pointers,
    interrupted downloads) whose config.json is empty or not real JSON — those
    are exactly what make transformers raise
    'Expecting value: line 1 column 1 (char 0)'.
    """
    import json
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and bool(data)
    except (OSError, ValueError):
        return False


def _has_real_weights(path: str) -> bool:
    for w in _MACBERT_WEIGHTS:
        wp = os.path.join(path, w)
        if os.path.isfile(wp) and os.path.getsize(wp) >= _MIN_WEIGHT_BYTES:
            return True
    return False


def _bad_json_files(path: str) -> list[str]:
    """Return JSON files in ``path`` that are broken (empty, parse error, stub).

    Rejects files whose content is clearly not a usable JSON file — size 0,
    unparseable text (XSym stubs), I/O errors — but *accepts* empty objects
    ``{}`` because that is a perfectly valid added_tokens.json (no extra tokens).
    """
    import json as _json
    bad = []
    try:
        names = [f for f in os.listdir(path) if f.endswith(".json")]
    except OSError:
        return bad
    for name in names:
        fp = os.path.join(path, name)
        try:
            if not os.path.isfile(fp) or os.path.getsize(fp) == 0:
                bad.append(name)
                continue
            with open(fp, "r", encoding="utf-8") as f:
                _json.load(f)
        except (OSError, ValueError):
            bad.append(name)
    return bad


def _is_macbert_dir(path: str) -> bool:
    """True if ``path`` holds a usable MacBERT model.

    Requires a valid config.json, real weights, and every present JSON file to
    be valid (an empty tokenizer JSON would crash the loader).
    """
    if not os.path.isdir(path):
        return False
    if not _valid_json_file(os.path.join(path, "config.json")):
        return False
    if not _has_real_weights(path):
        return False
    return not _bad_json_files(path)


def get_macbert_model_path() -> str | None:
    """Return a local directory holding a usable MacBERT model, or None.

    Lets users pre-download the model on another machine and drop the whole
    folder into ``models/macbert/`` (or ``models/macbert4csc-base-chinese/``),
    which is then loaded directly with no network access. Also recognises a
    proper HuggingFace cache snapshot under ``macbert_cache/``.
    """
    # 1) Explicit local model folders (simplest for users copying files over).
    for d in MODEL_SEARCH_DIRS:
        for name in ("macbert", "macbert4csc-base-chinese"):
            cand = os.path.join(d, name)
            if _is_macbert_dir(cand):
                return cand

    # 2) A HuggingFace cache snapshot, under any search dir's macbert_cache.
    #    HF stores it as macbert_cache[/hub]/models--*/snapshots/<hash>/, so we
    #    walk the whole cache tree and match the snapshots/<hash> layout.
    cache_dirs = [os.path.join(d, "macbert_cache") for d in MODEL_SEARCH_DIRS]
    for cache in _dedup(cache_dirs):
        if not os.path.isdir(cache):
            continue
        for root, _dirs, _files in os.walk(cache):
            if os.path.basename(os.path.dirname(root)) == "snapshots" \
                    and _is_macbert_dir(root):
                return root
    return None


def _has_xet_store() -> bool:
    """True if a macbert_cache/xet directory with data exists — a sign that the
    model was downloaded in HuggingFace Xet format and needs materialising."""
    for d in MODEL_SEARCH_DIRS:
        xet = os.path.join(d, "macbert_cache", "xet")
        if os.path.isdir(xet):
            try:
                if any(os.scandir(xet)):
                    return True
            except OSError:
                pass
    return False


def _macbert_snapshot_dirs() -> list[str]:
    """All snapshot directories that look like a MacBERT model (valid or not)."""
    out = []
    for d in MODEL_SEARCH_DIRS:
        cache = os.path.join(d, "macbert_cache")
        if not os.path.isdir(cache):
            continue
        for root, _dirs, files in os.walk(cache):
            if os.path.basename(os.path.dirname(root)) == "snapshots" \
                    and "config.json" in files:
                out.append(root)
    return out


def diagnose_macbert() -> str | None:
    """Explain why a present-but-unusable MacBERT model can't load, or None.

    Detects the common failure where the model was downloaded but its files are
    un-materialised pointer stubs (empty/invalid config.json, tiny weight files)
    — typically a HuggingFace Xet download that wasn't fully pulled.
    """
    # Look at every candidate model dir (explicit folders + cache snapshots).
    candidates = list(_macbert_snapshot_dirs())
    for d in MODEL_SEARCH_DIRS:
        for name in ("macbert", "macbert4csc-base-chinese"):
            cand = os.path.join(d, name)
            if os.path.isdir(cand):
                candidates.append(cand)

    for d in candidates:
        bad = _bad_json_files(d)
        weights_ok = _has_real_weights(d)
        if bad or not weights_ok:
            # If a Xet store holds the real bytes, the snapshot files are just
            # pointers — the data exists but isn't materialised into real files.
            if _has_xet_store():
                return (
                    "模型是以 HuggingFace Xet 格式下载的：真实数据在 macbert_cache/xet 里，"
                    "但 snapshots 下的文件只是指针，程序无法直接读取。\n\n"
                    "解决办法（任选其一）：\n"
                    "  1. 把完整的【实体】模型文件放到 models/macbert/ 目录：\n"
                    "     从 https://huggingface.co/shibing624/macbert4csc-base-chinese/tree/main\n"
                    "     逐个下载 pytorch_model.bin(约400MB)、config.json、vocab.txt、\n"
                    "     tokenizer_config.json、special_tokens_map.json；\n"
                    "  2. 或用命令行禁用 Xet 重新下载：\n"
                    "     set HF_HUB_DISABLE_XET=1 && huggingface-cli download \n"
                    "     shibing624/macbert4csc-base-chinese --local-dir 路径/models/macbert"
                )
            if bad:
                return (f"模型目录中有 JSON 文件为空或损坏：{', '.join(bad)}\n  位置：{d}\n"
                        "请从 HuggingFace 重新下载这些文件的实体版本覆盖。")
            return (f"模型目录中权重文件缺失或过小（可能是指针文件）：\n  {d}\n"
                    "请确认 pytorch_model.bin 或 model.safetensors 是完整实体文件。")
    return None


def is_macbert_cached() -> bool:
    """Whether a *usable* MacBERT model (config + weights) exists locally."""
    return get_macbert_model_path() is not None


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


def get_offline_model() -> str | None:
    """Return the best model that can run *right now* with no network, or None.

    Used for silent auto-load at startup: we must never auto-select a model that
    would try (and fail) to download on a machine that is offline or blocked.
    A model that only has its dependencies installed (e.g. MacBERT without its
    weights cached) is intentionally excluded here.
    """
    for key in _priority_keys():
        if is_model_ready_offline(key):
            return key
    return None


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
