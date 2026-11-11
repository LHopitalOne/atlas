"""Use case: add to a code graph the edges a precise index (SCIP) sees, and mark the ones it already had as checked.

Graphify reads code by its syntax: a call to `save()` is linked to the functions named `save`, some of them guesses.
A SCIP index knows which definition each use reaches. Its uses become edges between the graph's own nodes, so the
map gains what the syntax missed and every edge SCIP shows is marked as seen by it.
"""

from dataclasses import dataclass

from ..core.model import CodeGraph, Ref, Status
from ..core.references import Definition
from .ports import ReferenceIndex


@dataclass(frozen=True)
class ScipEdgeReport:
    """What a pass did: files read from the index, uses that reached a node of the graph, edges the graph already
    had (now checked), edges it gained, and guessed edges (inferred or ambiguous) in the files read that SCIP did not
    show."""

    files: int = 0
    uses: int = 0
    checked: int = 0
    added: int = 0
    unseen_guesses: int = 0


class ScipEdges:
    """A use's source is the graph symbol for the definition it sits in (the file, at module level or when the graph
    has no such symbol); its target is the graph symbol for the definition it reaches, matched by file, name and a
    line within SLACK of the index's (decorators and comments move a definition's line between tools). A use whose
    definition the graph has no symbol for (a library, a local variable, an attribute) adds nothing."""

    SLACK = 3  # lines a graph symbol's line may differ from the index's for the same definition
    GUESSES = frozenset({Status.INFERRED, Status.AMBIGUOUS})

    def __init__(self, index: ReferenceIndex):
        self._index = index
        self.report = ScipEdgeReport()

    def add(self, graph: CodeGraph) -> CodeGraph:
        symbols = self._symbols(graph)
        before = dict(graph.links)
        files = uses = 0
        covered = set()
        for (repo, path), f in sorted(graph.files.items()):
            if path not in self._index.files(repo):
                continue
            files += 1
            covered.add((repo, path))
            for use in self._index.uses(repo, path):
                target = self._node(symbols, self._index.definition(use.key))
                if target is None:
                    continue
                source = self._node(symbols, use.within) or f.ref
                if source != target:
                    uses += 1
                    graph.link(source, target, Status.MATCHED, checked=True)
        checked = sum(edge in graph.checked for edge in before)
        added = len(graph.links) - len(before)
        unseen = sum(
            status in self.GUESSES and (a.repo, a.path) in covered and (a, b) not in graph.checked
            for (a, b), status in before.items()
        )
        if files:
            graph.tools.add('SCIP')
        self.report = ScipEdgeReport(files, uses, checked, added, unseen)
        return graph

    @staticmethod
    def _symbols(graph):
        """{(repo, path, plain name): [(line, ref)]} for every symbol of the graph."""
        found = {}
        for f in graph.files.values():
            for s in f.symbols:
                found.setdefault((f.repo, f.path, ScipEdges.plain(s.name)), []).append(
                    (s.line, Ref(f.repo, f.path, s.id))
                )
        return found

    def _node(self, symbols, definition: Definition | None):
        if definition is None:
            return None
        candidates = symbols.get((definition.repo, definition.file, self.plain(definition.name)), [])
        near = [
            (abs(line - definition.line), ref) for line, ref in candidates if abs(line - definition.line) <= self.SLACK
        ]
        return min(near, key=lambda t: t[0])[1] if near else None

    @staticmethod
    def plain(label: str) -> str:
        """A symbol's bare name: Graphify writes 'save()' for a function and '.save()' for a method."""
        name = label.strip()
        name = name[:-2] if name.endswith('()') else name
        return name.rsplit('.', 1)[-1]
