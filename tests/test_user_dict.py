"""Tests for docproof.engine.user_dict module."""

import os
import tempfile
import textwrap

from docproof.engine.user_dict import UserDict


class TestUserDict:
    """Tests for UserDict whitelist functionality."""

    def test_empty_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = f.name
        try:
            ud = UserDict(path)
            assert ud.word_count == 0
            assert not ud.contains("test")
            assert ud.filter_errors([]) == []
        finally:
            os.unlink(path)

    def test_add_and_contains(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            ud = UserDict(path)
            assert ud.add_word("测试") is True
            assert ud.contains("测试") is True
            assert ud.word_count == 1
            # Adding duplicate returns False
            assert ud.add_word("测试") is False
            assert ud.word_count == 1
        finally:
            os.unlink(path)
            # Clean up any saved file
            if os.path.exists(path):
                os.unlink(path)

    def test_remove_word(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            ud = UserDict(path)
            ud.add_word("测试")
            assert ud.contains("测试")
            assert ud.remove_word("测试") is True
            assert not ud.contains("测试")
            assert ud.remove_word("不存在") is False
        finally:
            os.unlink(path)

    def test_filter_errors(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            ud = UserDict(path)
            ud.add_word("专有名词")

            # Create mock error items
            from docproof.engine.base_engine import ErrorItem
            errors = [
                ErrorItem(error="专有名词", correct="专用名词", start=0, end=4),
                ErrorItem(error="错别字", correct="错别字吗", start=5, end=8),
            ]
            filtered = ud.filter_errors(errors)
            assert len(filtered) == 1
            assert filtered[0].error == "错别字"
        finally:
            os.unlink(path)

    def test_loads_from_file(self):
        content = "# comment line\n测试词\n另一个词\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            ud = UserDict(path)
            assert ud.contains("测试词")
            assert ud.contains("另一个词")
            assert not ud.contains("# comment line")  # comments are skipped
            assert ud.word_count == 2
        finally:
            os.unlink(path)

    def test_reload(self):
        """Test that reload picks up external changes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write("初始词\n")
            path = f.name
        try:
            ud = UserDict(path)
            assert ud.contains("初始词")

            # Modify file externally
            with open(path, "w", encoding="utf-8") as f:
                f.write("初始词\n新词\n")

            ud.reload()
            assert ud.contains("新词")
            assert ud.word_count == 2
        finally:
            os.unlink(path)
