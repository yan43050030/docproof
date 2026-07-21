"""Shared pytest fixtures.

GUI tests run against Qt's offscreen platform so they work headlessly on CI.
If PySide6 isn't installed, GUI tests are skipped rather than failing.
"""

import os

import pytest

# Must be set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:  # pragma: no cover - depends on environment
    _HAS_QT = False


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the whole test session."""
    if not _HAS_QT:
        pytest.skip("PySide6 not available")
    app = QApplication.instance() or QApplication([])
    yield app


def pytest_configure(config):
    config.addinivalue_line("markers", "gui: tests that require a Qt application")
