"""Rule-based punctuation / normalization checker (fully offline, no deps).

Statistical and neural spellers (Kenlm, MacBERT) fix wrong *characters* but
ignore punctuation and formatting conventions. This engine adds a conservative,
high-precision pass for the mistakes those models miss:

* half-width ASCII punctuation used between Chinese characters (``,`` -> ``，``);
* stray spaces inserted between two Chinese characters;
* the same Chinese punctuation mark repeated (``，，`` -> ``，``).

Every rule only fires when both neighbours are Han characters (or the match is
unambiguous), so false positives on code, URLs, numbers and English text stay
rare. Findings are reported with ``category="punctuation"``.
"""

from __future__ import annotations

import re

from docproof.engine.base_engine import BaseEngine, ErrorItem

# A Han character (common + extension A). Deliberately excludes digits/letters.
_HAN = r"[㐀-鿿豈-﫿]"

# ASCII punctuation that should be full-width when sitting between Han chars.
_ASCII_TO_FULL = {
    ",": "，",
    ".": "。",
    ";": "；",
    ":": "：",
    "?": "？",
    "!": "！",
}

# Chinese punctuation marks that are (almost) never legitimately doubled.
_REPEATABLE_CJK = "，。、；："

_RE_ASCII_PUNCT = re.compile(
    rf"(?<={_HAN})([{re.escape(''.join(_ASCII_TO_FULL))}])(?={_HAN})"
)
_RE_HAN_SPACE = re.compile(rf"(?<={_HAN})([ 　]+)(?={_HAN})")
_RE_REPEAT_PUNCT = re.compile(rf"([{_REPEATABLE_CJK}])\1+")


class RuleEngine(BaseEngine):
    """Lightweight punctuation/normalization proofreading engine."""

    def __init__(self):
        super().__init__(name="rule")
        self._loaded = True  # no model to load

    def load(self) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        pass

    def correct(self, text: str) -> list[ErrorItem]:
        errors: list[ErrorItem] = []

        for m in _RE_ASCII_PUNCT.finditer(text):
            ch = m.group(1)
            errors.append(ErrorItem(
                error=ch, correct=_ASCII_TO_FULL[ch],
                start=m.start(1), end=m.end(1),
                category="punctuation", source="rule",
            ))

        for m in _RE_HAN_SPACE.finditer(text):
            errors.append(ErrorItem(
                error=m.group(1), correct="",
                start=m.start(1), end=m.end(1),
                category="punctuation", source="rule",
            ))

        for m in _RE_REPEAT_PUNCT.finditer(text):
            errors.append(ErrorItem(
                error=m.group(0), correct=m.group(1),
                start=m.start(), end=m.end(),
                category="punctuation", source="rule",
            ))

        errors.sort(key=lambda e: e.start)
        return errors
