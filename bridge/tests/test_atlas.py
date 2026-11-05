import json
import shutil
import subprocess
import unittest

from atlas_bridge.adapters import AtlasSpecPresenter, GraphifyReader
from atlas_bridge.core.model import CodeGraph, Kind, Symbol
from atlas_bridge.usecases.draw import FolderGrouping, MapDrawer

from .helpers import ATLAS, GRAPH


def spec(**kw):
    g = CodeGraph()
    GraphifyReader(g).read(GRAPH, 'shop')
    return AtlasSpecPresenter().present(MapDrawer(**kw).draw(g))


def validate(s):
    """Run Atlas's own validateSpec (src/model/spec.js) on a spec; returns the list of problems."""
    script = (
        "import {validateSpec} from './src/model/spec.js';"
        "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>"
        'console.log(JSON.stringify(validateSpec(JSON.parse(s)))))'
    )
    out = subprocess.run(
        ['node', '--input-type=module', '-e', script],
        cwd=ATLAS,
        check=True,
        input=json.dumps(s),
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


class PresentTest(unittest.TestCase):
    def test_hierarchy(self):
        s = spec()
        doms = s['repos'][0]['domains']
        self.assertEqual([d['name'] for d in doms], ['c0', 'c1'])
        self.assertEqual(doms[0]['services'][0]['name'], 'app.py')
        self.assertEqual(doms[0]['services'][0]['loc'], 'app.py:1')
        self.assertEqual(
            [(lf['name'], lf['kind'], lf['loc']) for lf in doms[0]['services'][0]['leaves']],
            [('main()', 1, 'app.py:3'), ('Server', 2, 'app.py:9')],
        )
        self.assertEqual(s['meta']['source'], 'Graphify 0.9.101')

    def test_ids_services_first_then_leaves(self):
        # services app.py=0, db.py=1; leaves main()=2, Server=3, URL=4, query()=5
        self.assertEqual(spec()['edges'], [[0, 1, 0], [2, 5, 0], [3, 4, 3]])

    def test_grouping_is_passed_through(self):
        self.assertEqual([d['name'] for d in spec(grouping=FolderGrouping())['repos'][0]['domains']], ['(root)', 'lib'])

    def test_same_names_get_numbered(self):
        g = CodeGraph()
        a, b = g.file('r', 'a/index.js'), g.file('r', 'b/index.js')
        a.symbols += [Symbol('f1', 'f()', Kind.FUNCTION, 2), Symbol('f2', 'f()', Kind.FUNCTION, 8)]
        svcs = AtlasSpecPresenter().present(MapDrawer().draw(g))['repos'][0]['domains'][0]['services']
        self.assertEqual([s['name'] for s in svcs], ['index.js', 'index.js (2)'])
        self.assertEqual([lf['name'] for lf in svcs[0]['leaves']], ['f()', 'f() (2)'])
        self.assertEqual(b.symbols, [])

    @unittest.skipUnless(shutil.which('node'), 'needs node')
    def test_atlas_accepts_it(self):
        self.assertEqual(validate(spec()), [])


if __name__ == '__main__':
    unittest.main()
