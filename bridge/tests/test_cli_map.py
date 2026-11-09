"""The one-command path: `atlas ./api ./web` and its parts (Graphify runner, merger, page)."""

import contextlib
import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

from atlas_bridge.adapters.graphify import GraphifyMerger, GraphifyRunner
from atlas_bridge.adapters.page import AtlasPage
from atlas_bridge.cli import AtlasApp, main
from atlas_bridge.cli.map import MapCommand
from atlas_bridge.core.errors import (
    ExtractionError,
    GraphifyFailedError,
    GraphifyUnavailableError,
    OutputError,
    PageTemplateError,
)

from .helpers import FIXTURES, load
from .test_atlas import validate

SHOP = os.path.join(FIXTURES, 'shop')


def load_text(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def fake_graphify(folder, code):
    """A graphify executable that copies the fixture graph of the repository it runs in, or fails with `code`."""
    path = os.path.join(folder, 'graphify')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(
            f'#!{sys.executable}\nimport os, shutil, sys\n'
            f'if {code}: print("boom", file=sys.stderr); sys.exit({code})\n'
            "os.makedirs('graphify-out', exist_ok=True)\n"
            f'fixtures = {os.path.join(FIXTURES, "graphify")!r}\n'
            "shutil.copy(os.path.join(fixtures, os.path.basename(os.getcwd()) + '.json'), 'graphify-out/graph.json')\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class Shop:
    """A copy of the shop fixture's two repositories in a temporary folder."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        for repo in ('api', 'web'):
            shutil.copytree(os.path.join(SHOP, repo), os.path.join(self.dir, repo))
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def atlas(self, graphify_code=0, *extra):
        out, err = self.path('atlas-out'), io.StringIO()
        exe = fake_graphify(self.dir, graphify_code)
        argv = [self.path('api'), self.path('web'), '-o', out, '--no-open', *extra]
        with mock.patch.object(GraphifyRunner, 'executable', return_value=exe), contextlib.redirect_stderr(err):
            code = AtlasApp().run(argv)
        return code, err.getvalue(), out


@unittest.skipUnless(os.name == 'posix', 'the fake graphify is a script with a shebang')
class AtlasCommandTest(unittest.TestCase):
    def test_maps_two_repositories_into_one_page(self):
        with Shop() as shop:
            code, log, out = shop.atlas()
            self.assertEqual(code, 0, log)
            spec = load(os.path.join(out, 'spec.json'))
            html = load_text(os.path.join(out, 'atlas.html'))
            links = load(os.path.join(out, 'links.json'))
        self.assertEqual(validate(spec), [])
        self.assertEqual([r['name'] for r in spec['repos']], ['api', 'web'])
        self.assertEqual(spec['meta']['title'], 'api, web')
        self.assertNotIn(AtlasPage.MARKER, html)
        self.assertIn('"title":"api, web"', html)
        self.assertEqual(sum(lk['status'] == 'matched' for lk in links['links']), 2)
        self.assertIn('not checked with SCIP', log)

    def test_reuses_an_existing_graph(self):
        with Shop() as shop:
            shop.atlas()
            code, log, _ = shop.atlas(1)  # graphify would fail now, but is not run
        self.assertEqual(code, 0, log)
        self.assertNotIn('mapping', log.split('atlas: mapping')[1])

    def test_graphify_failure_still_writes_the_map(self):
        with Shop() as shop:
            code, log, out = shop.atlas(3)
            spec = load(os.path.join(out, 'spec.json'))
        self.assertEqual(code, 0, log)
        self.assertIn('graphify could not map api: boom', log)
        self.assertEqual(validate(spec), [])
        self.assertTrue(spec['edges'], 'the links still show without code graphs')

    def test_scip_without_tools_is_one_line_per_repo(self):
        with Shop() as shop, mock.patch('shutil.which', return_value=None):
            code, log, _ = shop.atlas(0, '--verify')
        self.assertEqual(code, 0, log)
        self.assertIn('no index written; links are not checked with SCIP', log)

    def test_missing_folder_is_an_input_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(AtlasApp().run(['/no/such/repo', '--no-open']), 2)
        self.assertIn("atlas: no repository folder at '/no/such/repo'", err.getvalue())

    def test_also_a_bridge_subcommand(self):
        with Shop() as shop:
            exe = fake_graphify(shop.dir, 0)
            out = shop.path('o')
            with (
                mock.patch.object(GraphifyRunner, 'executable', return_value=exe),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                main(['map', shop.path('api'), '-o', out, '--no-open', '--title', 'API'])
            self.assertEqual(load(os.path.join(out, 'spec.json'))['meta']['title'], 'API')


class PartsTest(unittest.TestCase):
    def test_folders_with_one_name_are_told_apart(self):
        from atlas_bridge.cli import RepositoryInput

        repos = MapCommand.unique([RepositoryInput('app', 'a/app'), RepositoryInput('app', 'b/app')])
        self.assertEqual([r.name for r in repos], ['app', 'app-2'])

    def test_merger_prefixes_ids_and_tags_repositories(self):
        merged = GraphifyMerger().merge([('api', load(os.path.join(FIXTURES, 'graphify', 'api.json')))])
        self.assertTrue(all(n['id'].startswith('api::') and n['repo'] == 'api' for n in merged['nodes']))
        ids = {n['id'] for n in merged['nodes']}
        self.assertTrue(all(e['source'].startswith('api::') for e in merged['links']))
        self.assertTrue(any(e['target'] in ids for e in merged['links']))

    def test_page_escapes_the_spec(self):
        with tempfile.TemporaryDirectory() as d:
            template = os.path.join(d, 't.html')
            with open(template, 'w', encoding='utf-8') as f:
                f.write(f'<p>{AtlasPage.SLOT}</p>')
            html = AtlasPage(template).render({'title': '</script><b>'})
        self.assertEqual(
            html, '<p><script type="application/json" id="selfGraph">{"title":"\\u003c/script>\\u003cb>"}</script></p>'
        )

    def test_page_template_is_shipped_and_missing_is_an_output_error(self):
        self.assertIn(AtlasPage.SLOT, load_text(AtlasPage.TEMPLATE))
        with self.assertRaises(PageTemplateError) as e:
            AtlasPage('/nowhere.html').render({})
        self.assertIsInstance(e.exception, OutputError)
        self.assertIn('npm run build:page', str(e.exception))

    def test_runner_errors(self):
        self.assertIsInstance(GraphifyFailedError('api', 'x'), ExtractionError)
        with mock.patch('os.path.isfile', return_value=False), mock.patch('shutil.which', return_value=None):
            self.assertRaises(GraphifyUnavailableError, GraphifyRunner.executable)


if __name__ == '__main__':
    unittest.main()
