"""Base classes shared by the adapters that turn use-case results into an outside format."""

from abc import ABC, abstractmethod


class Presenter(ABC):
    """Turns a use-case result into the plain data (dicts and lists) of an outside format, ready to dump as JSON."""

    @abstractmethod
    def present(self, result) -> dict: ...
