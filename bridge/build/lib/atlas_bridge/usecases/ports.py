"""Ports: what the use cases need from the outside world, as abstract classes adapters implement."""

from abc import ABC, abstractmethod

from ..core.evidence import Assumption, Verdict
from ..core.http import Extraction


class Extractor(ABC):
    """Finds the HTTP routes a repository serves and the requests it sends."""

    @abstractmethod
    def extract(self, repo: str, root: str) -> Extraction:
        """repo: the repository's name in the results; root: its folder."""


class DefinitionOracle(ABC):
    """Knows, from a precise index (a compiler's view of the code), where each name in a repository is defined."""

    @abstractmethod
    def covers(self, repo: str) -> bool:
        """Whether there is an index for this repository at all."""

    @abstractmethod
    def check(self, repo: str, assumption: Assumption) -> Verdict:
        """What the index says of one assumption made while reading `repo`."""
