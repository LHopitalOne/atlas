"""Ports: what the use cases need from the outside world, as abstract classes adapters implement."""

from abc import ABC, abstractmethod

from ..core.http import Extraction


class Extractor(ABC):
    """Finds the HTTP routes a repository serves and the requests it sends."""

    @abstractmethod
    def extract(self, repo: str, root: str) -> Extraction:
        """repo: the repository's name in the results; root: its folder."""
