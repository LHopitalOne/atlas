"""Integration: the real Graphify CLI on the shop fixture, through the bridge, into Atlas's validator.

Runs only with ATLAS_INTEGRATION=1 and the graphify command installed (CI pins the version the fixtures were
made with: bridge/requirements-dev.txt).
"""

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest

from atlas_bridge.cli import main

from ..helpers import FIXTURES, GOLDEN, load
from ..test_atlas import validate

GRAPHIFY = shutil.which('graphify')
ENABLED = os.environ.get('ATLAS_INTEGRATION') == '1' and GRAPHIFY and shutil.which('node')


@unittest.skipUnless(ENABLED, 'set ATLAS_INTEGRATION=1; needs graphify and node')
class GraphifyLiveTest(unittest.TestCase):
    def test_shop_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            graphs = []
            for repo in ('api', 'web'):
                path = os.path.join(d, repo)
                shutil.copytree(os.path.join(FIXTURES, 'shop', repo), path)
                env = {**os.environ, 'GRAPHIFY_NO_AUTO_REFRESH': '1'}
                subprocess.run([GRAPHIFY, 'update', '.'], cwd=path, env=env, check=True, capture_output=True)
                graphs.append(os.path.join(path, 'graphify-out', 'graph.json'))
            out = os.path.join(d, 'spec.json')
            with contextlib.redirect_stderr(io.StringIO()):
                main(['spec', *graphs, '--title', 'Shop, mapped by Graphify', '-o', out])
            spec = load(out)
        self.assertEqual(validate(spec), [])
        golden = load(GOLDEN)
        if spec['meta']['source'] != golden['meta']['source']:
            self.skipTest(f'golden spec was made with {golden["meta"]["source"]}, this is {spec["meta"]["source"]}')
        self.assertEqual(spec, golden)


if __name__ == '__main__':
    unittest.main()
