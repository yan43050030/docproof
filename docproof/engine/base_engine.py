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

    def __repr__(self):
        return f"ErrorItem({self.error!r} → {self.correct!r} @[{self.start}:{self.end}])"


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
