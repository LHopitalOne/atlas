"""The map command's steps: Graphify graphs, HTTP links, the Atlas spec and the page. Each step that can fail says
so in one line and hands the next step what it has, so a map is always written."""

import os
import time

from ..adapters.atlas import AtlasSpecPresenter
from ..adapters.graphify import GraphifyLinkWriter, GraphifyMerger, GraphifyReader, GraphifyRunner
from ..adapters.linkfile import LinkFilePresenter
from ..adapters.page import AtlasPage
from ..core.errors import BridgeError, GraphFormatError
from ..core.http import Extraction
from ..core.model import CodeGraph
from ..usecases.draw import GROUPINGS, MapDrawer
from ..usecases.link import LinkFinder, LinkReport
from .inputs import GraphInput, JsonFile
from .scipcheck import ScipCheck


class MapPipeline:
    def __init__(self, options, report):
        """options: parsed map arguments (out_dir, refresh, aliases, include_tests, verify, sandbox, group, title)."""
        self._o = options
        self._report = report
        self._runner = GraphifyRunner()

    def run(self, repos) -> str:
        """Every step for these repositories (cli.inputs.RepositoryInput); returns the page's path."""
        os.makedirs(self._o.out_dir, exist_ok=True)
        graph = self._timed('graphify', lambda: GraphifyMerger().merge([(r.name, self._graph(r)) for r in repos]))
        links = self._timed('links', lambda: self._links(repos))
        graph = GraphifyLinkWriter(graph).present(links)
        JsonFile.write(self._out('graph.json'), graph)
        spec = self._timed('map', lambda: self._spec(graph))
        JsonFile.write(self._out('spec.json'), spec)
        return AtlasPage().write(self._out('atlas.html'), spec)

    def _graph(self, repo):
        """The repository's Graphify graph: the one already in graphify-out/ unless --refresh, else a new one; an
        empty graph when Graphify cannot map it, so its links still show."""
        try:
            if self._o.refresh or not self._runner.has_graph(repo.path):
                self._report(f'  graphify  {repo.name}: mapping {repo.path} ...')
                self._runner.update(repo.name, repo.path)
            path = self._runner.graph_path(repo.path)
            data = GraphInput(repo.name, path).load()
            if not isinstance(data, dict) or not isinstance(data.get('nodes'), list):
                raise GraphFormatError(path, 'it has no "nodes" list')
        except BridgeError as e:
            self._report(f'  graphify  {repo.name}: no code graph, {e}')
            return {'nodes': [], 'links': []}
        self._report(f'  graphify  {repo.name}: {len(data["nodes"]):,} nodes ({os.path.relpath(path)})')
        return data

    def _links(self, repos):
        names = [r.name for r in repos]
        try:
            from ..adapters.treesitter import TreeSitterExtractor  # the tree-sitter packages

            extraction, extractor = Extraction(), TreeSitterExtractor()
            for repo in repos:
                extraction.extend(extractor.extract(repo.name, repo.path))
            links = LinkFinder(names, self._o.aliases, include_tests=self._o.include_tests).find(extraction)
        except (BridgeError, ImportError) as e:
            self._report(f'  links     none found: {e}')
            return []
        if self._o.verify:
            links = ScipCheck(self._o.out_dir, self._report, self._o.sandbox).verify(repos, links)
        else:
            self._report('  links     not checked with SCIP (add --verify; needs Node.js and/or rust-analyzer)')
        report = LinkReport(names, extraction, links)
        JsonFile.write(self._out('links.json'), LinkFilePresenter().present(report), indent=1)
        found = sum(link.route is not None for link in links)
        self._report(f'  links     {found} between repositories, {len(links) - found} requests with no route found')
        return links

    def _spec(self, graph):
        code = CodeGraph()
        GraphifyReader(code).read(graph, 'repo', source=self._out('graph.json'))
        spec = AtlasSpecPresenter(self._o.title).present(MapDrawer(GROUPINGS[self._o.group]).draw(code))
        files = sum(len(d['services']) for r in spec['repos'] for d in r['domains'])
        self._report(f'  map       {len(spec["repos"])} repositories, {files:,} files, {len(spec["edges"]):,} links')
        return spec

    def _timed(self, step, work):
        start = time.monotonic()
        result = work()
        self._report(f'  {step:<9} done in {time.monotonic() - start:.1f}s')
        return result

    def _out(self, name):
        return os.path.join(self._o.out_dir, name)
