"""The map command's steps: Graphify graphs, HTTP links, the Atlas spec and the page. Each step that can fail says
so in one line and hands the next step what it has, so a map is always written."""

import os
import time

from ..adapters.atlas import AtlasSpecPresenter
from ..adapters.graphify import GraphifyLinkWriter, GraphifyMerger, GraphifyReader, GraphifyRunner
from ..adapters.linkfile import LinkFilePresenter
from ..adapters.page import AtlasPage
from ..core.errors import BridgeError, GraphFormatError, OutputWriteError
from ..core.http import Extraction
from ..core.model import CodeGraph
from ..usecases.draw import GROUPINGS, MapDrawer
from ..usecases.link import LinkFinder, LinkReport
from .budget import MapBudget
from .inputs import GraphInput, JsonFile
from .links import LinksCommand
from .scipcheck import ScipCheck


class MapPipeline:
    MAX_GRAPH_JSON_NODES = 200_000  # PostHog's 760,000-node merged graph is a 1.2 GB file nobody asked for

    def __init__(self, options, report):
        """options: parsed map arguments (out_dir, refresh, aliases, include_tests, verify, sandbox, group, title,
        graph_json, within)."""
        self._o = options
        self._report = report
        self._runner = GraphifyRunner(self._still_mapping)
        self._current = ''

    def run(self, repos) -> str:
        """Every step for these repositories (cli.inputs.RepositoryInput); returns the page's path."""
        self._save('', None)  # the output folder, before the slow steps
        graph = self._timed('graphify', lambda: GraphifyMerger().merge([(r.name, self._graph(r)) for r in repos]))
        links = self._timed('links', lambda: self._links(repos))
        graph = GraphifyLinkWriter(graph).present(links)
        if self._o.graph_json or len(graph['nodes']) <= self.MAX_GRAPH_JSON_NODES:
            self._save('graph.json', graph)
        else:
            self._report(
                f'  graph     graph.json not written: {len(graph["nodes"]):,} nodes (add --graph-json to write it)'
            )
        spec = self._timed('map', lambda: self._spec(graph))
        self._save('spec.json', spec)
        return self._save('atlas.html', spec, AtlasPage().write)

    def _graph(self, repo):
        """The repository's Graphify graph: the one already in graphify-out/ unless --refresh, else a new one; an
        empty graph when Graphify cannot map it, so its links still show."""
        try:
            if self._o.refresh or not self._runner.has_graph(repo.path):
                self._report(f'  graphify  {repo.name}: mapping {repo.path} ...')
                self._current = repo.name
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

    def _still_mapping(self, seconds):
        hint = ', large repositories take Graphify a while; map a subfolder for a quicker look' if seconds > 100 else ''
        minutes, rest = divmod(int(seconds), 60)
        self._report(f'  graphify  {self._current}: still mapping, {minutes}m{rest:02d}s so far{hint}')

    def _links(self, repos):
        names = [r.name for r in repos]
        try:
            from ..adapters.treesitter import TreeSitterExtractor  # the tree-sitter packages

            extraction, extractor = Extraction(), TreeSitterExtractor()
            for repo in repos:
                extraction.extend(extractor.extract(repo.name, repo.path))
            rules = LinksCommand._rules(self._o.within)  # the same rule order as `links --within`
            links = LinkFinder(names, self._o.aliases, self._o.include_tests, rules).find(extraction)
        except (BridgeError, ImportError) as e:
            self._report(f'  links     none found: {e}')
            return []
        if self._o.verify:
            links = ScipCheck(self._o.out_dir, self._report, self._o.sandbox).verify(repos, links)
        else:
            self._report('  links     not checked with SCIP (add --verify; needs Node.js and/or rust-analyzer)')
        report = LinkReport(names, extraction, links)
        self._save('links.json', LinkFilePresenter().present(report))
        found = [link for link in links if link.route is not None]
        inside = sum(link.source == link.target for link in found)
        self._report(
            f'  links     {len(found) - inside} between repositories, {inside} inside one, '
            f'{len(links) - len(found)} requests with no route found'
        )
        return links

    def _spec(self, graph):
        code = CodeGraph()
        GraphifyReader(code).read(graph, 'repo', source=self._out('graph.json'))
        if MapBudget().fit(code):
            self._report(
                f'  map       over {MapBudget.MAX_NODES:,} files and symbols: functions and classes are folded into '
                'their files, except at the ends of HTTP links'
            )
        spec = AtlasSpecPresenter(self._o.title).present(MapDrawer(GROUPINGS[self._o.group]).draw(code))
        files = sum(len(d['services']) for r in spec['repos'] for d in r['domains'])
        self._report(f'  map       {len(spec["repos"])} repositories, {files:,} files, {len(spec["edges"]):,} links')
        return spec

    def _timed(self, step, work):
        start = time.monotonic()
        result = work()
        self._report(f'  {step:<9} done in {time.monotonic() - start:.1f}s')
        return result

    def _save(self, name, data, write=JsonFile.write):
        """Write one output file (or, with no name, make the output folder)."""
        path = self._out(name)
        try:
            if name:
                write(path, data)
            else:
                os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise OutputWriteError(path, e.strerror or str(e)) from e
        return path

    def _out(self, name):
        return os.path.join(self._o.out_dir, name)
