"""Tests for docproof.document.position_mapper module."""

from unittest.mock import MagicMock

from docproof.document.position_mapper import PositionMapper, TextSpan


def _make_paragraph_mock(text: str, para_index: int = 0):
    """Create a mock paragraph with runs matching the text."""
    para = MagicMock()
    run = MagicMock()
    run.text = text
    para.runs = [run]
    para.text = text
    return para, run


class TestPositionMapper:
    """Tests for character position mapping."""

    def test_empty_paragraphs(self):
        mapper = PositionMapper()
        mapper.build([])
        assert mapper.total_chars == 0
        assert mapper.paragraph_count == 0

    def test_single_paragraph(self):
        mapper = PositionMapper()
        para, _ = _make_paragraph_mock("你好世界")
        mapper.build([para])

        assert mapper.paragraph_count == 1
        # "你好世界" = 4 chars + 1 newline separator = 5
        assert mapper.total_chars == 5

    def test_char_to_span_within_text(self):
        mapper = PositionMapper()
        para, _ = _make_paragraph_mock("测试文本")
        mapper.build([para])

        span = mapper.char_to_span(0)
        assert span is not None
        assert span.paragraph_index == 0
        assert span.run_index == 0
        assert span.offset_in_run == 0

        span = mapper.char_to_span(2)
        assert span is not None
        assert span.paragraph_index == 0
        assert span.offset_in_run == 2

    def test_char_to_span_out_of_range(self):
        mapper = PositionMapper()
        para, _ = _make_paragraph_mock("test")
        mapper.build([para])

        assert mapper.char_to_span(-1) is None
        # "test" = 4 chars, map has 4 entries (plus newline at pos 4 not in map)
        assert mapper.char_to_span(4) is None
        assert mapper.char_to_span(100) is None

    def test_multiple_paragraphs(self):
        mapper = PositionMapper()
        p1, _ = _make_paragraph_mock("第一段")
        p2, _ = _make_paragraph_mock("第二段")
        mapper.build([p1, p2])

        assert mapper.paragraph_count == 2
        # "第一段"(3) + \n(1) + "第二段"(3) + \n(1) = 8
        assert mapper.total_chars == 8

        # First paragraph chars
        span = mapper.char_to_span(0)
        assert span.paragraph_index == 0

        # Second paragraph chars (after "第一段" + \n = 4)
        span = mapper.char_to_span(4)
        assert span is not None
        assert span.paragraph_index == 1

    def test_get_paragraph_range(self):
        mapper = PositionMapper()
        p1, _ = _make_paragraph_mock("AB")
        p2, _ = _make_paragraph_mock("CDE")
        mapper.build([p1, p2])

        start, end = mapper.get_paragraph_range(0)
        assert start == 0
        assert end == 2  # "AB"

        start, end = mapper.get_paragraph_range(1)
        assert start == 3  # after "AB" + \n
        assert end == 6  # 3 + "CDE"

    def test_get_paragraph_range_invalid(self):
        mapper = PositionMapper()
        start, end = mapper.get_paragraph_range(999)
        assert start == 0
        assert end == 0

    def test_get_paragraph_text(self):
        mapper = PositionMapper()
        p1, _ = _make_paragraph_mock("段落一")
        p2, _ = _make_paragraph_mock("段落二")
        mapper.build([p1, p2])

        assert mapper.get_paragraph_text(0) == "段落一"
        assert mapper.get_paragraph_text(1) == "段落二"
        assert mapper.get_paragraph_text(999) == ""

    def test_multiple_runs_in_paragraph(self):
        """Test that runs within a paragraph are handled."""
        mapper = PositionMapper()
        para = MagicMock()
        run1 = MagicMock()
        run1.text = "Hello"
        run2 = MagicMock()
        run2.text = " World"
        para.runs = [run1, run2]
        para.text = "Hello World"
        mapper.build([para])

        assert mapper.total_chars == 12  # "Hello World"(11) + \n

        # First run chars
        span = mapper.char_to_span(0)
        assert span.run_index == 0
        assert span.offset_in_run == 0

        # Second run chars
        span = mapper.char_to_span(5)
        assert span.run_index == 1
        assert span.offset_in_run == 0  # space
