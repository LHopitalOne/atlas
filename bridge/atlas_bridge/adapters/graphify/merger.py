"""Adapter: several repositories' Graphify graphs as one, in the shape `graphify merge-graphs` writes.

Node ids become 'repo::id' and every node carries `repo`, so GraphifyLinkWriter can attach links to the symbols
they start in, and GraphifyReader puts each file in its own repository.
"""


class GraphifyMerger:
    SEP = '::'

    def merge(self, graphs: list[tuple[str, dict]]) -> dict:
        """graphs: (repository name, parsed graph.json) pairs."""
        out = {'directed': True, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}
        for repo, data in graphs:
            out['graph'] = out['graph'] or dict(data.get('graph') or {})
            out['nodes'] += [self._node(repo, n) for n in data.get('nodes') or []]
            out['links'] += [self._edge(repo, e) for e in data.get('links') or data.get('edges') or []]
        return out

    def _id(self, repo, node_id):
        return f'{repo}{self.SEP}{node_id}'

    def _node(self, repo, node):
        return {**node, 'id': self._id(repo, node['id']), 'repo': node.get('repo') or repo}

    def _edge(self, repo, edge):
        return {**edge, 'source': self._id(repo, edge.get('source')), 'target': self._id(repo, edge.get('target'))}
