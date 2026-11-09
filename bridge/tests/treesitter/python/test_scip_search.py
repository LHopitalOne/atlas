import textwrap
import unittest

from atlas_bridge.core.callgraph import Function, Target
from atlas_bridge.usecases.ports import CallGraph

from .support import extract, requests_

CLIENT = textwrap.dedent(
    """
    import requests

    class Api:
        def get(self, path):
            return requests.get(f'https://svc/api/{path}')
    """
)
VIEWS = textwrap.dedent(
    """
    def load(api):
        return api.get('users/')

    def in_a_test(self):
        return self.client.get('/api/health/')

    def timeout_second(s):
        return s.get('https://svc/api/ping/', 5)
    """
)
FILES = {'svc/client.py': CLIENT, 'svc/views.py': VIEWS}
API_GET = 'svc/Api#get().'


def line(source, text):
    return next(i for i, s in enumerate(source.splitlines(), 1) if text in s)


class FakeIndex(CallGraph):
    """What SCIP would say about these two files."""

    def __init__(self):
        start = line(CLIENT, 'def get')
        self.functions = [Function(API_GET, 'get', 'svc', 'svc/client.py', start, start + 1)]
        own = Target(API_GET, True, True)
        self.names = {
            ('svc/client.py', line(CLIENT, 'requests.get'), 'get'): Target('`requests.api`/get().', False, False),
            ('svc/views.py', line(VIEWS, "api.get('users/')"), 'get'): own,
            ('svc/views.py', line(VIEWS, 'self.client.get'), 'get'): Target(
                '`django.test.client`/Client#get().', False, True
            ),
            ('svc/views.py', line(VIEWS, 's.get('), 'get'): Target('`requests.sessions`/Session#get().', False, True),
        }

    def enclosing(self, repo, file, line):
        return next((f for f in self.functions if f.file == file and f.start <= line <= f.end), None)

    def callers(self, function):
        return []

    def resolves(self, repo, file, line, name):
        found = self.names.get((file, line, name))
        return frozenset({found}) if found else frozenset()


class ScipSearchTest(unittest.TestCase):
    def test_names_alone(self):
        found = requests_(extract(FILES))
        self.assertNotIn(('GET', '/api/users'), found)  # 'get' is too common to follow into another file by name
        self.assertIn(('GET', '/api/health'), found)  # a test client taken for an HTTP client
        self.assertNotIn(('GET', '/api/ping'), found)  # taken for mapping.get(key, default)

    def test_the_index_decides_what_it_knows(self):
        found = requests_(extract(FILES, graph=FakeIndex()))
        self.assertIn(('GET', '/api/users'), found)  # the index says api.get reaches Api.get
        self.assertNotIn(('GET', '/api/health'), found)  # Django's test client, not an HTTP library
        self.assertIn(('GET', '/api/ping'), found)  # requests' Session.get, whatever the arguments look like


if __name__ == '__main__':
    unittest.main()
