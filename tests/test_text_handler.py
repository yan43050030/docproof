"""Tests for the plain-text handler."""

import os
import tempfile

from docproof.document.text_handler import TextHandler
from docproof.engine.base_engine import ErrorItem


def _write(text: str) -> str:
    path = tempfile.mktemp(suffix=".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class TestTextHandler:
    def test_load_and_full_text(self):
        path = _write("第一行\n第二行有错字")
        try:
            h = TextHandler(path)
            h.load()
            assert h.get_full_text() == "第一行\n第二行有错字"
        finally:
            os.remove(path)

    def test_apply_corrections(self):
        text = "第一行\n第二行有错字"
        path = _write(text)
        try:
            h = TextHandler(path)
            h.load()
            idx = text.index("错字")
            h.apply_corrections([ErrorItem("错字", "错别字", idx, idx + 2)],
                                markup=False)
            out = tempfile.mktemp(suffix=".txt")
            h.save(out)
            with open(out, encoding="utf-8") as f:
                assert f.read() == "第一行\n第二行有错别字"
            os.remove(out)
        finally:
            os.remove(path)

    def test_multiple_corrections_offsets(self):
        text = "甲错和乙错"
        path = _write(text)
        try:
            h = TextHandler(path)
            h.load()
            errs = [
                ErrorItem("错", "对", 1, 2),
                ErrorItem("错", "对", 4, 5),
            ]
            h.apply_corrections(errs, markup=False)
            assert h.get_full_text() == "甲对和乙对"
        finally:
            os.remove(path)
