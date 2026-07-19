"""Run-level editing primitives for python-docx paragraphs.

Corrections target a character span ``[start, end)`` measured against a
paragraph's proofread text (concatenation of run texts). These helpers split
runs at span boundaries so the span lines up with whole runs, then apply one of
three edits while preserving the original run formatting:

* :func:`replace_span`  — clean replacement (used for "apply corrections").
* :func:`markup_span`   — visible colored markup (red strikethrough + blue fix).
* :func:`revise_span`   — genuine Word tracked changes (``w:del`` + ``w:ins``),
  which Word/WPS can accept or reject natively.

Splitting a run deep-copies its ``w:rPr`` so character formatting (font, size,
bold, color, ...) is retained on every produced fragment.
"""

from __future__ import annotations

import copy
import datetime
import itertools

from docx.oxml.ns import qn
from docx.shared import RGBColor
from docx.text.run import Run

RED = RGBColor(0xDC, 0x26, 0x26)
BLUE = RGBColor(0x25, 0x63, 0xEB)
GRAY = RGBColor(0x88, 0x88, 0x88)

# Monotonic id source for w:ins / w:del revision elements.
_rev_id = itertools.count(1)

DEFAULT_AUTHOR = "DocProof"


def _run_ranges(para) -> tuple[list, list[tuple[int, int]]]:
    """Return (runs, ranges) where ranges[i] = (start, end) local offsets."""
    runs = list(para.runs)
    ranges = []
    local = 0
    for run in runs:
        length = len(run.text or "")
        ranges.append((local, local + length))
        local += length
    return runs, ranges


def _split_run(run, k: int):
    """Split ``run`` at local offset k (0 < k < len). Returns the new right run.

    The right fragment is inserted immediately after ``run`` and inherits the
    same run properties (``w:rPr``).
    """
    text = run.text or ""
    new_r = copy.deepcopy(run._r)
    run._r.addnext(new_r)
    new_run = Run(new_r, run._parent)
    run.text = text[:k]
    new_run.text = text[k:]
    return new_run


def _ensure_boundary(para, offset: int) -> None:
    """Ensure a run boundary exists at ``offset`` (splitting a run if needed)."""
    if offset <= 0:
        return
    _, ranges = _run_ranges(para)
    for (s, e) in ranges:
        if s == offset:
            return  # boundary already present
        if s < offset < e:
            runs, _ = _run_ranges(para)
            # find the run object at this range
            for run, (rs, re) in zip(runs, ranges):
                if rs == s:
                    _split_run(run, offset - s)
                    return
            return


def isolate_runs(para, start: int, end: int) -> list:
    """Split runs so that ``[start, end)`` aligns to whole runs; return them."""
    if end <= start:
        return []
    _ensure_boundary(para, end)
    _ensure_boundary(para, start)
    runs, ranges = _run_ranges(para)
    return [
        run for run, (s, e) in zip(runs, ranges)
        if s >= start and e <= end and s < end and e > s
    ]


def _copy_font(src_run, dst_run) -> None:
    """Copy visible character formatting from src_run to dst_run."""
    sf, df = src_run.font, dst_run.font
    if sf.name:
        df.name = sf.name
    if sf.size:
        df.size = sf.size
    if sf.bold is not None:
        df.bold = sf.bold
    if sf.italic is not None:
        df.italic = sf.italic


# ---- public operations ----

def replace_span(para, start: int, end: int, replacement: str) -> bool:
    """Replace ``[start, end)`` with ``replacement``, keeping run formatting."""
    runs = isolate_runs(para, start, end)
    if not runs:
        return False
    runs[0].text = replacement
    for r in runs[1:]:
        r.text = ""
    return True


def markup_span(para, start: int, end: int, error: str, correct: str) -> bool:
    """Add visible revision markup: strike the error, append the correction.

    Result reads like ``错词 → 正词`` with the error in red strikethrough and
    the correction in blue bold, while preserving the base font.
    """
    runs = isolate_runs(para, start, end)
    if not runs:
        return False
    base = runs[0]
    for r in runs:
        r.font.color.rgb = RED
        r.font.strike = True

    last_r = runs[-1]._r

    arrow_r = copy.deepcopy(base._r)
    last_r.addnext(arrow_r)
    arrow = Run(arrow_r, base._parent)
    _copy_font(base, arrow)
    arrow.text = " → "
    arrow.font.strike = False
    arrow.font.bold = False
    arrow.font.color.rgb = GRAY

    corr_r = copy.deepcopy(base._r)
    arrow._r.addnext(corr_r)
    corr = Run(corr_r, base._parent)
    _copy_font(base, corr)
    corr.text = correct
    corr.font.strike = False
    corr.font.color.rgb = BLUE
    corr.font.bold = True
    return True


def _rewrap_text_tag(r_el, new_tag: str) -> None:
    """Rename every ``w:t`` child of a run element to ``new_tag`` (e.g. delText)."""
    want = qn("w:t")
    target = qn(new_tag)
    for child in r_el.findall(want):
        child.tag = target
        child.set(qn("xml:space"), "preserve")


def revise_span(
    para, start: int, end: int, error: str, correct: str,
    author: str = DEFAULT_AUTHOR, when: str | None = None,
) -> bool:
    """Apply a genuine tracked change (``w:del`` + ``w:ins``) over the span.

    Word and WPS render this as a real revision that can be accepted or
    rejected. Deleted text keeps its formatting inside ``w:del``; the inserted
    correction inherits the base run's ``w:rPr`` inside ``w:ins``.
    """
    runs = isolate_runs(para, start, end)
    if not runs:
        return False

    base_r_template = copy.deepcopy(runs[0]._r)
    parent = runs[0]._r.getparent()
    if parent is None:
        return False

    if when is None:
        when = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    del_el = parent.makeelement(qn("w:del"), {})
    del_el.set(qn("w:id"), str(next(_rev_id)))
    del_el.set(qn("w:author"), author)
    del_el.set(qn("w:date"), when)

    ins_el = parent.makeelement(qn("w:ins"), {})
    ins_el.set(qn("w:id"), str(next(_rev_id)))
    ins_el.set(qn("w:author"), author)
    ins_el.set(qn("w:date"), when)

    first_r = runs[0]._r
    first_r.addprevious(del_el)
    del_el.addnext(ins_el)

    # Move the deleted runs into <w:del>, converting w:t -> w:delText.
    for r in runs:
        r_el = r._r
        parent.remove(r_el)
        _rewrap_text_tag(r_el, "w:delText")
        del_el.append(r_el)

    # Build the inserted correction run inside <w:ins>.
    _rewrap_text_tag(base_r_template, "w:t")
    ins_el.append(base_r_template)
    corr = Run(base_r_template, runs[0]._parent)
    corr.text = correct
    return True
