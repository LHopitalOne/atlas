"""Collectors: each finds one kind of route or request in a workspace."""

from abc import ABC, abstractmethod

from ....core.http import ANY, Call, Extraction, PathTemplate, Route
from .workspace import Workspace


class Collector(ABC):
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    @abstractmethod
    def collect(self) -> Extraction: ...


class RouteCollector(Collector):
    """Finds the routes one framework declares."""

    framework = ''

    def route(self, source, line, path: str, methods=frozenset({ANY}), handler='', name=''):
        return Route(
            self.workspace.repo,
            source.path,
            line,
            PathTemplate.parse(path),
            frozenset(methods),
            handler,
            name,
            self.framework,
        )


class CallCollector(Collector):
    """Finds one idiom of sending HTTP requests (or of handing URLs to other services)."""

    def call(self, source, line, path: str | None, method=ANY, function='', hints=(), test=False, **kind):
        template = PathTemplate.parse(path) if path is not None else None
        return Call(
            self.workspace.repo, source.path, line, template, method, function, frozenset(hints), test=test, **kind
        )
