"""Local file logging for troubleshooting.

Writes rotating logs to ~/.docproof/logs/docproof.log and captures uncaught
exceptions so users can attach a log file when reporting problems.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys

from docproof.config import USER_DATA_DIR

LOG_DIR = os.path.join(USER_DATA_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "docproof.log")

_initialized = False


def init_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up file logging (idempotent). Returns the app logger."""
    global _initialized
    logger = logging.getLogger("docproof")
    if _initialized:
        return logger

    logger.setLevel(level)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        logger.addHandler(handler)
    except OSError:
        # Logging must never break the app (e.g. read-only home dir).
        logger.addHandler(logging.NullHandler())

    # Record uncaught exceptions, then defer to the default hook.
    previous_hook = sys.excepthook

    def _log_uncaught(exc_type, exc_value, exc_tb):
        if not issubclass(exc_type, KeyboardInterrupt):
            logger.error("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _log_uncaught
    _initialized = True
    return logger


def get_logger(name: str = "docproof") -> logging.Logger:
    return logging.getLogger(name)
