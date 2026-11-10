"""Use case: describe the files of a map with a model, the files that matter most first, within a budget."""

from dataclasses import dataclass

from ..core.descriptions import Description
from ..core.model import CodeGraph
from .ports import FileCase, FileDescriber


@dataclass(frozen=True)
class EnrichReport:
    asked: int
    described: int


class Enricher:
    """Picks the files to describe: not tests or tooling (`skip`), the ends of the links between services first
    (what the map is about), then the files with the most functions and classes, at most MAX_FILES; asks the
    describer once per file. A description is kept only when its role is one of Description.ROLES."""

    MAX_FILES = 2000  # files described in one run, to bound cost and time
    MAX_TAGS = 4

    def __init__(self, describer: FileDescriber, skip=lambda path: False, max_files: int = MAX_FILES):
        self._describer = describer
        self._skip = skip
        self._max = max_files
        self.report = EnrichReport(0, 0)

    def describe(self, graph: CodeGraph, linked: frozenset = frozenset()) -> dict[tuple[str, str], Description]:
        """{(repo, path): Description} for the chosen files. `linked`: (repo, path) of files at an end of a link."""
        files = [f for f in graph.files.values() if not self._skip(f.path)]
        files.sort(key=lambda f: ((f.repo, f.path) not in linked, -len(f.symbols), f.repo, f.path))
        cases = [FileCase(f.repo, f.path) for f in files[: self._max]]
        found = self._describer.describe(cases) if cases else []
        out = {}
        for case, d in zip(cases, found, strict=True):
            if d is not None and d.summary and d.role in Description.ROLES:
                out[(case.repo, case.path)] = Description(d.summary, d.role, tuple(d.tags[: self.MAX_TAGS]))
        self.report = EnrichReport(len(cases), len(out))
        return out
