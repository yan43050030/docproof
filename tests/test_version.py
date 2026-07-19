"""Tests for docproof.version."""

from docproof.version import __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_version_not_empty():
    assert len(__version__) > 0


def test_version_parseable():
    """Version should follow semver-like format (X.Y.Z)."""
    parts = __version__.split(".")
    assert len(parts) >= 2
    for p in parts:
        assert p.isdigit(), f"Version part '{p}' is not numeric"
