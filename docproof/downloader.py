"""Optional in-app model downloader.

This is an *addition* to the manual flow (copy URL → download in a browser →
drop the file into models/). When it can't reach the network, the UI falls back
to telling the user to download on another machine and copy the file over.

Downloads stream to a temporary file next to the target and are renamed into
place only on success, so a cancelled or failed download never leaves a
half-written model file.
"""

from __future__ import annotations

import os
import ssl
import urllib.request
from typing import Callable

from PySide6.QtCore import QThread, Signal

# Prefer the environment CA bundle if one is configured (e.g. corporate proxy).
_CA_BUNDLE = (os.environ.get("REQUESTS_CA_BUNDLE")
              or os.environ.get("SSL_CERT_FILE")
              or os.environ.get("CURL_CA_BUNDLE"))


def _ssl_context() -> ssl.SSLContext:
    if _CA_BUNDLE and os.path.exists(_CA_BUNDLE):
        return ssl.create_default_context(cafile=_CA_BUNDLE)
    return ssl.create_default_context()


def download(url: str, dest_path: str,
             progress: Callable[[int, int], None] | None = None,
             should_stop: Callable[[], bool] | None = None) -> None:
    """Download ``url`` to ``dest_path`` atomically.

    ``progress(done_bytes, total_bytes)`` is called as data arrives
    (total_bytes may be 0 if the server doesn't report a length).
    Raises on failure; raises InterruptedError if cancelled.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp_path = dest_path + ".part"
    ctx = _ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "DocProof"})

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(tmp_path, "wb") as f:
                while True:
                    if should_stop is not None and should_stop():
                        raise InterruptedError("下载已取消")
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
        os.replace(tmp_path, dest_path)
    except BaseException:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


class DownloadThread(QThread):
    """Runs a model download off the UI thread."""

    progress = Signal(int, int)   # (done_bytes, total_bytes)
    finished_ok = Signal(str)     # dest_path
    failed = Signal(str)          # error message

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._dest = dest_path
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            download(self._url, self._dest,
                     progress=lambda d, t: self.progress.emit(d, t),
                     should_stop=lambda: self._stop)
            self.finished_ok.emit(self._dest)
        except InterruptedError:
            pass  # user cancelled — no error dialog
        except Exception as e:
            self.failed.emit(str(e))
