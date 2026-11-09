import unittest

from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.link import LinkFinder
from atlas_bridge.usecases.within import WithinRepoRule

P = PathTemplate.parse
ROUTES = [
    Route('app', 'server/urls.py', 1, P('/api/users/{pk}')),
    Route('app', 'server/urls.py', 2, P('/api/users/{pk}/tokens')),
    Route('app', 'server/urls.py', 3, P('/{*path}')),  # the page catch-all
    Route('other', 'urls.py', 1, P('/api/orders/{id}')),
]
WITHIN = (*LinkFinder.RULES[:-1], WithinRepoRule, LinkFinder.RULES[-1])


def links(*calls, rules=WITHIN):
    found = LinkFinder(['app', 'other'], rules=rules).find(Extraction(list(ROUTES), list(calls)))
    return [(lk.target, str(lk.route.path) if lk.route else None, lk.status) for lk in found]


def call(path, file='web/src/api.ts', **kw):
    return Call('app', file, 1, P(path), 'GET', **kw)


class WithinRepoTest(unittest.TestCase):
    def test_browser_code_reaches_its_own_server(self):
        self.assertEqual(links(call('/api/users/{id}')), [('app', '/api/users/{pk}', Status.MATCHED)])
        self.assertEqual(links(call('/api/users/{id}'), rules=LinkFinder.RULES), [])  # off by default

    def test_what_it_does_not_link(self):
        self.assertEqual(links(call('/api/users/{id}', file='server/jobs.py')), [])  # not browser code
        self.assertEqual(links(call('/pages/about')), [])  # only the catch-all would take it
        self.assertEqual(links(call('/api/users/{*rest}')), [])  # an unknown rest, several routes fit
        self.assertEqual(links(call('/{x}')), [])  # no fixed word

    def test_another_repository_named_wins(self):
        named = call('/api/orders/{id}', hints=frozenset({'other_client'}))
        self.assertEqual(links(named), [('other', '/api/orders/{id}', Status.MATCHED)])


if __name__ == '__main__':
    unittest.main()
