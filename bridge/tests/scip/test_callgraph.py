import unittest

from atlas_bridge.adapters.scip import ScipCallGraph, ScipIndex, ScipOracle, ScipSymbol
from atlas_bridge.core.evidence import Assumption, Verdict

from .builder import ScipBuilder

# The SDK's own index writes its src/ layout; the service's index writes the installed package.
RAW_GET = 'scip-python python sdk 2.1 `src.sdk.tasks.raw`/RawTasks#get().'
GET = 'scip-python python sdk 2.1 `src.sdk.tasks.client`/Tasks#get().'
GET_INSTALLED = 'scip-python python sdk 2.1.7 `sdk.tasks.client`/Tasks#get().'
OTHER_INSTALLED = 'scip-python python sdk 2.1.7 `sdk.users.client`/Users#list().'
SERVICE_FN = 'scip-python python ml 0 `ml.model`/Model#fit().'
CLIENT_CLASS = 'scip-python python sdk 2.1.7 `sdk.client`/Client#'


def sdk_index():
    b = ScipBuilder()
    b.occurrence('src/sdk/tasks/raw.py', 10, RAW_GET, definition=True, span=(10, 20))
    b.occurrence('src/sdk/tasks/raw.py', 15, RAW_GET)  # a recursive call: not a caller
    b.occurrence('src/sdk/tasks/client.py', 30, GET, definition=True, span=(30, 40))
    b.occurrence('src/sdk/tasks/client.py', 35, RAW_GET)
    return ScipIndex(b.build(), 'sdk.scip')


def service_index():
    b = ScipBuilder()
    b.occurrence('ml/model.py', 5, SERVICE_FN, definition=True, span=(5, 50))
    b.occurrence('ml/model.py', 12, GET_INSTALLED)
    b.occurrence('ml/model.py', 13, OTHER_INSTALLED)
    b.occurrence('ml/model.py', 14, CLIENT_CLASS)
    return ScipIndex(b.build(), 'ml.scip')


class SymbolKeyTest(unittest.TestCase):
    def test_keys_ignore_package_version_and_source_root(self):
        self.assertEqual(ScipSymbol.key(GET), ScipSymbol.key(GET_INSTALLED))
        self.assertEqual(ScipSymbol.key(GET), '`sdk.tasks.client`/Tasks#get().')
        self.assertEqual(ScipSymbol.key('local 3'), 'local 3')
        self.assertTrue(ScipSymbol.is_callable(GET))
        self.assertFalse(ScipSymbol.is_callable(CLIENT_CLASS))
        self.assertFalse(ScipSymbol.is_callable('local 3'))


class CallGraphTest(unittest.TestCase):
    def setUp(self):
        self.graph = ScipCallGraph({'sdk': [sdk_index()], 'ml': [service_index()]}, {'sdk'})

    def test_enclosing_function(self):
        fn = self.graph.enclosing('sdk', 'src/sdk/tasks/raw.py', 12)
        self.assertEqual((fn.name, fn.start, fn.end, fn.key), ('get', 10, 20, '`sdk.tasks.raw`/RawTasks#get().'))
        self.assertIsNone(self.graph.enclosing('sdk', 'src/sdk/tasks/raw.py', 25))
        self.assertIsNone(self.graph.enclosing('nope', 'x.py', 1))

    def test_callers_across_repositories(self):
        raw = self.graph.enclosing('sdk', 'src/sdk/tasks/raw.py', 12)
        self.assertEqual(
            [(s.repo, s.file, s.line) for s in self.graph.callers(raw)], [('sdk', 'src/sdk/tasks/client.py', 35)]
        )
        get = self.graph.enclosing('sdk', 'src/sdk/tasks/client.py', 35)
        self.assertEqual(
            [(s.repo, s.line) for s in self.graph.callers(get)], [('ml', 12)]
        )  # not Users.list, not Client


class CrossRepoOracleTest(unittest.TestCase):
    def test_a_call_into_the_library_is_confirmed_there(self):
        oracle = ScipOracle({'sdk': [sdk_index()], 'ml': [service_index()]})
        into = Assumption('ml/model.py', 12, 'get', 'src/sdk/tasks/client.py', 30, 40, target_repo='sdk')
        self.assertIs(oracle.check('ml', into), Verdict.CONFIRMED)
        wrong = Assumption('ml/model.py', 12, 'get', 'src/sdk/tasks/raw.py', 10, 20, target_repo='sdk')
        self.assertIs(oracle.check('ml', wrong), Verdict.CONTRADICTED)
        nothing = Assumption('ml/model.py', 40, 'get', 'src/sdk/tasks/client.py', 30, 40, target_repo='sdk')
        self.assertIs(oracle.check('ml', nothing), Verdict.UNKNOWN)
        inside = Assumption(
            'src/sdk/tasks/client.py', 35, 'get', 'src/sdk/tasks/raw.py', 10, 20, repo='sdk', target_repo='sdk'
        )
        self.assertIs(oracle.check('ml', inside), Verdict.CONFIRMED)  # a hop inside the library, checked there


if __name__ == '__main__':
    unittest.main()
