"""Multiprocessing helpers for Kenlm parallel proofreading.

Kenlm detection is pure-Python and single-threaded, so large documents benefit
from splitting paragraphs across CPU cores. Each worker process loads the Kenlm
model once (cached at module scope) and proofreads assigned line batches.

Only Kenlm is parallelised — MacBERT/torch would need to reload a ~400MB model
per process, which is not worth it; it uses batched inference instead.

Everything here degrades gracefully: if a pool can't be created or a worker
fails, the caller falls back to serial processing.
"""

from __future__ import annotations

import os

# Per-process Corrector cache: model_path -> Corrector instance.
_WORKER_CACHE: dict = {}


def _get_corrector(model_path: str):
    # Never construct with a missing path: pycorrector would fall back to
    # downloading its 2.95GB default model, which fails offline.
    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"model not found: {model_path}")
    corr = _WORKER_CACHE.get(model_path)
    if corr is None:
        # Make sure the bundled pycorrector is importable inside the worker.
        from docproof.config import init_config
        init_config()
        from pycorrector.corrector import Corrector
        corr = Corrector(language_model_path=model_path)
        _WORKER_CACHE[model_path] = corr
    return corr


def _proofread_chunk(args: tuple) -> list[tuple]:
    """Worker entry: proofread one text chunk.

    args = (model_path, base_offset, text)
    returns list of (error, correct, global_start) tuples.
    """
    model_path, base_offset, text = args
    try:
        corr = _get_corrector(model_path)
        result = corr.correct(text)
        return [(e, c, base_offset + p) for e, c, p in result.get("errors", [])]
    except Exception:
        # A failed chunk yields nothing rather than crashing the whole run.
        return []


def default_worker_count() -> int:
    cpu = os.cpu_count() or 1
    return max(1, min(cpu - 1, 4)) if cpu > 1 else 1
