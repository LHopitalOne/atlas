"""Adapter in: Graphify's graph.json (NetworkX node-link data, already parsed) into the code graph model.

  file node   a node whose label is its source file's name; it stands for the file itself
  symbols     every other node with a source file: functions, classes, constants, doc sections
  community   the Graphify community most of a file's nodes belong to
  links       every relation except the structural ones (a file contains its symbols, a class its methods);
              EXTRACTED -> matched, AMBIGUOUS -> ambiguous, INFERRED -> inferred
Nodes without a source file (external modules) and comment ("rationale") nodes are left out.
"""

from ...core.errors import GraphFormatError
from ...core.model import CodeGraph, Ref, Status, Symbol
from .node import GraphifyNode


class GraphifyReader:
    STRUCTURAL = frozenset({'contains', 'method', 'rationale_for'})
    STATUS = {'EXTRACTED': Status.MATCHED, 'AMBIGUOUS': Status.AMBIGUOUS, 'INFERRED': Status.INFERRED}
    SKIP_TYPES = frozenset({'rationale'})

    def __init__(self, graph: CodeGraph):
        self._graph = graph

    def read(self, data: dict, repo: str, source: str = 'input'):
        """Add one graph.json to the graph. `repo` names it unless its nodes carry a `repo` (merge-graphs output)."""
        nodes = self._nodes(data, source)
        version = (data.get('graph') or {}).get('graphify_version')
        self._graph.tools.add(f'Graphify {version}' if version else 'Graphify')
        refs = self._add_files(nodes, repo)
        for e in data.get('links') or data.get('edges') or []:
            a, b = refs.get(e.get('source')), refs.get(e.get('target'))
            if a and b and e.get('relation') not in self.STRUCTURAL:
                self._graph.link(a, b, self.STATUS.get(e.get('confidence'), Status.INFERRED))

    @staticmethod
    def _nodes(data, source):
        if not isinstance(data, dict) or not isinstance(data.get('nodes'), list):
            raise GraphFormatError(source, 'it has no "nodes" list')
        bad = next((n for n in data['nodes'] if not isinstance(n, dict) or 'id' not in n), None)
        if bad is not None:
            raise GraphFormatError(source, f'a node has no id: {str(bad)[:80]}')
        return [GraphifyNode(n) for n in data['nodes']]

    def _add_files(self, nodes, repo):
        refs, by_file = {}, {}
        for n in nodes:
            if not n.source_file or n.data.get('file_type') in self.SKIP_TYPES:
                continue
            f = self._graph.file(n.repo or repo, n.source_file)
            by_file.setdefault(f.ref, (f, []))[1].append(n)
            if n.is_file:
                refs[n.id] = f.ref
            else:
                f.symbols.append(Symbol(n.id, n.label, n.kind, n.line))
                refs[n.id] = Ref(f.repo, f.path, n.id)
        for f, file_nodes in by_file.values():
            f.community = GraphifyNode.majority_community(file_nodes)
            f.symbols.sort(key=lambda s: (s.line, s.name))
        return refs
