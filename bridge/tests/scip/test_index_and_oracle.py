import os
import tempfile
import unittest

from atlas_bridge.adapters.scip import ScipIndex, ScipOracle
from atlas_bridge.core.errors import ScipFormatError
from atlas_bridge.core.evidence import Assumption, Verdict

from .builder import ScipBuilder

POOL = 'scip-python python s 0 `s.snuba`/_snuba_pool.'
OTHER = 'scip-python python s 0 `s.other`/_snuba_pool.'
LIB = 'scip-python python requests 2 `requests`/Session#'
TRAIT = 'rust-analyzer cargo relay 1 services/upstream/UpstreamQuery#'


def index(typed=False):
    b = ScipBuilder(typed)
    b.occurrence('s/snuba.py', 590, POOL, definition=True)
    b.occurrence('s/other.py', 3, OTHER, definition=True)
    b.occurrence('s/rpc.py', 465, POOL).occurrence('s/rpc.py', 466, OTHER).occurrence('s/rpc.py', 467, LIB)
    b.occurrence('s/up.rs', 1, TRAIT, definition=True).occurrence('s/impl.rs', 73, TRAIT)
    return ScipIndex(b.build(), 'test.scip')


def at(line, name, target='', start=0, end=0, file='s/rpc.py'):
    return Assumption(file, line, name, target, start, end)


class ScipIndexTest(unittest.TestCase):
    def test_documents_lines_and_definitions(self):
        for typed in (False, True):
            ix = index(typed)
            self.assertEqual(sorted(ix.paths), ['s/impl.rs', 's/other.py', 's/rpc.py', 's/snuba.py', 's/up.rs'])
            self.assertEqual([o.symbol for o in ix.at('s/rpc.py', 465)], [POOL])
            self.assertEqual(ix.definitions(POOL), [('s/snuba.py', 590)])
            self.assertTrue(ix.defined_in(POOL, 's/snuba.py', 580, 600))
            self.assertFalse(ix.defined_in(POOL, 's/snuba.py', 1, 10))
            self.assertEqual(ix.at('missing.py', 1), [])
            self.assertIsNone(ix.document('missing.py'))

    def test_line_one_survives_typed_ranges(self):
        self.assertEqual([o.line for o in index(typed=True).at('s/up.rs', 1)], [1])

    def test_bad_files(self):
        with self.assertRaises(ScipFormatError):
            ScipIndex(b'', 'empty.scip')
        with self.assertRaises(ScipFormatError):
            ScipIndex(ScipBuilder._len(2, ScipBuilder._varint_field(4, 1)), 'nopath.scip')
        with self.assertRaises(ScipFormatError):
            ScipIndex.read('/no/such/index.scip')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'i.scip')
            with open(path, 'wb') as f:
                f.write(ScipBuilder().occurrence('a.py', 1, POOL).build())
            self.assertEqual(ScipIndex.read(path).paths, ['a.py'])


class ScipOracleTest(unittest.TestCase):
    def setUp(self):
        self.oracle = ScipOracle({'s': [index()]})

    def test_verdicts(self):
        self.assertEqual(self.oracle.check('s', at(465, '_snuba_pool', 's/snuba.py', 590, 603)), Verdict.CONFIRMED)
        self.assertEqual(self.oracle.check('s', at(466, '_snuba_pool', 's/snuba.py', 590, 603)), Verdict.CONTRADICTED)
        self.assertEqual(self.oracle.check('s', at(465, 'nothing', 's/snuba.py', 590, 603)), Verdict.UNKNOWN)
        self.assertEqual(self.oracle.check('s', at(467, 'Session', 's/snuba.py', 1, 9)), Verdict.UNKNOWN)  # library

    def test_without_a_target_any_definition_in_the_repo_will_do(self):
        self.assertEqual(self.oracle.check('s', at(73, 'UpstreamQuery', file='s/impl.rs')), Verdict.CONFIRMED)
        self.assertEqual(self.oracle.check('s', at(467, 'Session')), Verdict.UNKNOWN)

    def test_coverage_and_several_indexes(self):
        self.assertTrue(self.oracle.covers('s'))
        self.assertFalse(self.oracle.covers('x'))
        self.assertEqual(self.oracle.check('x', at(465, '_snuba_pool')), Verdict.UNKNOWN)
        two = ScipOracle({'s': [ScipIndex(ScipBuilder().occurrence('z.py', 1, LIB).build()), index()]})
        self.assertEqual(two.check('s', at(465, '_snuba_pool', 's/snuba.py', 590, 603)), Verdict.CONFIRMED)


if __name__ == '__main__':
    unittest.main()
