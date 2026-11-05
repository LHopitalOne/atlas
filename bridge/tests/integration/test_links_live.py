"""Integration: real Graphify graphs of the shop fixture, merged, with HTTP links added, drawn by Atlas.

Runs only with ATLAS_INTEGRATION=1 and the graphify command installed (see test_graphify_live.py).
"""

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest

from atlas_bridge.cli import main

from ..helpers import FIXTURES, load
from ..test_atlas import validate
from .test_graphify_live import ENABLED, GRAPHIFY


@unittest.skipUnless(ENABLED, 'set ATLAS_INTEGRATION=1; needs graphify and node')
class LinksLiveTest(unittest.TestCase):
    def test_graphify_merge_links_atlas(self):
        env = {**os.environ, 'GRAPHIFY_NO_AUTO_REFRESH': '1'}
        with tempfile.TemporaryDirectory() as d:
            for repo in ('api', 'web'):
                shutil.copytree(os.path.join(FIXTURES, 'shop', repo), os.path.join(d, repo))
                subprocess.run(
                    [GRAPHIFY, 'update', '.'], cwd=os.path.join(d, repo), env=env, check=True, capture_output=True
                )
            merged = os.path.join(d, 'merged.json')
            graphs = [os.path.join(d, r, 'graphify-out', 'graph.json') for r in ('api', 'web')]
            subprocess.run(
                [GRAPHIFY, 'merge-graphs', *graphs, '--out', merged], env=env, check=True, capture_output=True
            )
            out, spec = os.path.join(d, 'with-links.json'), os.path.join(d, 'spec.json')
            with contextlib.redirect_stderr(io.StringIO()):
                main(
                    [
                        'links',
                        f'{d}/api',
                        f'{d}/web',
                        '-o',
                        os.path.join(d, 'links.json'),
                        '--graph',
                        merged,
                        '--graphify-out',
                        out,
                    ]
                )
                main(['spec', out, '-o', spec])
            with_links = load(out)
            spec_data = load(spec)
            # graphify itself can walk from the web client into the API through the new edges
            path = subprocess.run(
                [GRAPHIFY, 'path', 'placeOrder()', 'POST /orders', '--graph', out],
                env=env,
                capture_output=True,
                text=True,
            )
        http = [e for e in with_links['links'] if e['relation'] == 'calls_http']
        self.assertEqual({e['source'] for e in http}, {'web::src_api_placeorder', 'web::src_api_loadorder'})
        self.assertEqual(path.returncode, 0, path.stdout + path.stderr)
        self.assertEqual(validate(spec_data), [])
        self.assertEqual([r['name'] for r in spec_data['repos']], ['api', 'web'])


if __name__ == '__main__':
    unittest.main()
