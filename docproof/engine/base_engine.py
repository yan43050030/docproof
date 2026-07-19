"""Base class for proofreading engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ErrorItem:
    """A single proofreading error."""

    error: str  # wrong text
    correct: str  # corrected text
    start: int  # character offset in source text
    end: int  # character offset (exclusive)
    category: str = "spelling"  # spelling | punctuation | grammar
    source: str = ""  # engine that produced it (optional)

    def __repr__(self):
        return f"ErrorItem({self.error!r} → {self.correct!r} @[{self.start}:{self.end}] {self.category})"


# Human-readable labels for categories (used by the UI and reports).
CATEGORY_LABELS = {
    "spelling": "错别字",
    "punctuation": "标点/规范",
    "grammar": "语法",
}


class BaseEngine(ABC):
    """Abstract proofreading engine."""

    def __init__(self, name: str = "base"):
        self.name = name
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def load(self) -> bool:
        """Load the engine. Returns True on success."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release resources."""
        ...

    @abstractmethod
    def correct(self, text: str) -> list[ErrorItem]:
        """Run proofreading on text and return list of errors."""
        ...

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r})"
