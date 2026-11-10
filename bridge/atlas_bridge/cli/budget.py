"""Keeps a map within what the Atlas page draws smoothly: past MAX_NODES files and symbols, symbols are folded into
their files, except in files at either end of an HTTP link or of a link across repositories."""

from ..core.model import CodeGraph, Ref


class MapBudget:
    MAX_NODES = 100_000  # Atlas stays smooth to about 100,000 nodes (README)
    ENDPOINT = '::http:'  # in the id of an endpoint node GraphifyLinkWriter adds

    def __init__(self, max_nodes: int = MAX_NODES):
        self._max = max_nodes

    def fit(self, graph: CodeGraph, keep: frozenset = frozenset()) -> bool:
        """Fold symbols into files when the graph is over budget; True when it did. `keep`: more (repo, path) files
        whose symbols stay, such as both ends of the links the map proves."""
        symbols = sum(len(f.symbols) for f in graph.files.values())
        if len(graph.files) + symbols <= self._max:
            return False
        keep = self._link_ends(graph) | set(keep)
        for key, f in graph.files.items():
            if key not in keep:
                f.symbols = []
        kept = {(f.repo, f.path, s.id) for f in graph.files.values() for s in f.symbols}
        links, graph.links = graph.links, {}
        for (a, b), status in links.items():
            graph.link(self._lift(a, kept), self._lift(b, kept), status)
        return True

    def _link_ends(self, graph):
        files = set()
        for a, b in graph.links:
            if a.repo != b.repo or self.ENDPOINT in (b.symbol or ''):
                files.update({(a.repo, a.path), (b.repo, b.path)})
        return files

    @staticmethod
    def _lift(ref, kept):
        if ref.symbol is None or (ref.repo, ref.path, ref.symbol) in kept:
            return ref
        return Ref(ref.repo, ref.path)
