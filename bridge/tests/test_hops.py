import unittest

from atlas_bridge.core.callgraph import Function, Site
from atlas_bridge.core.http import Call, PathTemplate
from atlas_bridge.usecases.hops import LibraryHops
from atlas_bridge.usecases.ports import CallGraph

P = PathTemplate.parse
RAW = Function('raw.get', 'get', 'sdk', 'sdk/raw.py', 10, 20)
TASKS = Function('tasks.get', 'get', 'sdk', 'sdk/tasks.py', 30, 40)
FIT = Function('model.fit', 'fit', 'ml', 'ml/model.py', 1, 90)


class FakeGraph(CallGraph):
    """sdk/raw.py:15 sends the request inside RawTasks.get; Tasks.get calls it at sdk/tasks.py:35; the service calls
    Tasks.get twice, and Tasks.get calls itself."""

    FUNCTIONS = {('sdk', 'sdk/raw.py'): RAW, ('sdk', 'sdk/tasks.py'): TASKS, ('ml', 'ml/model.py'): FIT}
    CALLERS = {
        'raw.get': [Site('sdk', 'sdk/tasks.py', 35)],
        'tasks.get': [Site('ml', 'ml/model.py', 12), Site('ml', 'ml/model.py', 60), Site('sdk', 'sdk/tasks.py', 38)],
    }

    def enclosing(self, repo, file, line):
        fn = self.FUNCTIONS.get((repo, file))
        return fn if fn is not None and fn.start <= line <= fn.end else None

    def callers(self, function):
        return self.CALLERS.get(function.key, [])

    def resolves(self, repo, file, line, name):
        return frozenset()


def request(path='/api/tasks/{id}/', line=15, **kw):
    return Call('sdk', 'sdk/raw.py', line, P(path), 'GET', hints=frozenset({'httpx_client'}), **kw)


class LibraryHopsTest(unittest.TestCase):
    def hops(self, *calls):
        return LibraryHops(FakeGraph(), {'sdk'}).calls(list(calls))

    def test_a_library_request_moves_to_the_service_lines_that_reach_it(self):
        moved = self.hops(request())
        self.assertEqual(
            [(c.repo, c.file, c.line) for c in moved], [('ml', 'ml/model.py', 12), ('ml', 'ml/model.py', 60)]
        )
        first = moved[0]
        self.assertEqual((first.method, str(first.path), first.function), ('GET', '/api/tasks/{id}', 'fit'))
        self.assertTrue({'httpx_client', 'get', 'sdk'} <= first.hints)
        into, inside = first.assumptions
        self.assertEqual(
            (into.file, into.line, into.target_file, into.repo, into.target_repo),
            ('ml/model.py', 12, 'sdk/tasks.py', '', 'sdk'),
        )
        self.assertEqual((inside.file, inside.repo, inside.target_file), ('sdk/tasks.py', 'sdk', 'sdk/raw.py'))

    def test_what_is_not_moved(self):
        self.assertEqual(self.hops(request('/data/{data}')), [])  # too little of the path is known
        self.assertEqual(self.hops(request(test=True)), [])
        self.assertEqual(self.hops(request(line=99)), [])  # in no function
        service = Call('ml', 'ml/model.py', 3, P('/api/x/y'), 'GET')
        self.assertEqual(self.hops(service), [])  # not a library's request


if __name__ == '__main__':
    unittest.main()
