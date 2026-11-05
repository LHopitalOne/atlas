import unittest

from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.link import LinkFinder, ServiceNames

P = PathTemplate.parse
SNQL = Route('snuba', 'views.py', 10, P('/{dataset}/snql'), frozenset({'GET', 'POST'}))
STORAGE = Route('snuba', 'views.py', 20, P('/{storage}'), frozenset({'DELETE'}))
HEALTH = Route('snuba', 'views.py', 30, P('/health'), frozenset({'GET'}))
DSYMS = Route('sentry', 'urls.py', 5, P('/api/0/projects/{o}/{p}/files/dsyms'), name='dsym-files')
OWN = Route('sentry', 'urls.py', 6, P('/api/0/organizations/{o}'))


def call(path, method='ANY', hints=(), repo='sentry', **kw):
    return Call(repo, 'client.py', 7, P(path) if path else None, method, 'f', frozenset(hints), **kw)


def links(*calls, routes=(SNQL, STORAGE, HEALTH, DSYMS, OWN), aliases=None, **kw):
    return LinkFinder(['sentry', 'snuba', 'symbolicator'], aliases, **kw).find(Extraction(list(routes), list(calls)))


def summary(found):
    return [(lk.source, lk.target, str(lk.route.path) if lk.route else None, lk.status) for lk in found]


class ServiceNamesTest(unittest.TestCase):
    def test_resolve(self):
        names = ServiceNames(['sentry', 'snuba', 'relay'], {'upstream': 'sentry'})
        self.assertEqual(names.resolve(['_snuba_pool'], exclude='sentry'), {'snuba'})
        self.assertEqual(names.resolve(['UpstreamQuery'], exclude='relay'), {'sentry'})
        self.assertEqual(names.resolve(['src/sentry/x.py'], exclude='sentry'), set())


class FindLinksTest(unittest.TestCase):
    def test_named_target_one_route(self):
        self.assertEqual(
            summary(links(call('/{d}/snql', 'POST', ['_snuba_pool']), call('/{s}', 'DELETE', ['snuba_pool']))),
            [('sentry', 'snuba', '/{dataset}/snql', Status.MATCHED), ('sentry', 'snuba', '/{storage}', Status.MATCHED)],
        )

    def test_unmatched_and_ambiguous(self):
        both = Route('snuba', 'views.py', 40, P('/{x}/snql'), frozenset({'POST'}))
        found = summary(
            links(call('/nothing/here', 'GET', ['snuba']), call('/a/snql', 'POST', ['snuba']), routes=(SNQL, both))
        )
        self.assertEqual(found[0], ('sentry', 'snuba', None, Status.UNMATCHED))
        self.assertEqual({f[3] for f in found[1:]}, {Status.AMBIGUOUS})
        self.assertEqual(len(found), 3)

    def test_catch_all_is_not_a_match(self):
        catch_all = Route('snuba', 'urls.py', 60, P('/{*path}'))
        found = links(call('/api/0/relays/metrics', 'POST', ['snuba']), routes=(catch_all,))
        self.assertEqual(summary(found), [('sentry', 'snuba', None, Status.UNMATCHED)])
        self.assertIn('catch-all /{*path}', found[0].reason)

    def test_last_parameter_may_hold_slashes(self):
        sub = Route(
            'snuba', 'views.py', 70, P('/{dataset}/{entity}/subscriptions/{partition}/{key}'), frozenset({'DELETE'})
        )
        found = links(call('/{d}/{e}/subscriptions/{subscription_id}', 'DELETE', ['snuba']), routes=(sub,))
        self.assertEqual(summary(found), [('sentry', 'snuba', str(sub.path), Status.INFERRED)])
        two = Route('snuba', 'views.py', 71, P('/{a}/{b}/subscriptions/{c}/{d}'), frozenset({'DELETE'}))
        found = links(call('/{d}/{e}/subscriptions/{subscription_id}', 'DELETE', ['snuba']), routes=(sub, two))
        self.assertEqual({f[3] for f in summary(found)}, {Status.AMBIGUOUS})

    def test_no_hint_needs_a_literal_fit_outside_its_own_repo(self):
        self.assertEqual(summary(links(call('/health'))), [])  # one literal segment proves too little
        two = Route('snuba', 'views.py', 50, P('/tests/drop'))
        self.assertEqual(
            summary(links(call('/tests/drop'), routes=(two,))), [('sentry', 'snuba', '/tests/drop', Status.INFERRED)]
        )
        mine = Route('sentry', 'urls.py', 9, P('/tests/drop'))
        self.assertEqual(summary(links(call('/tests/drop'), routes=(two, mine))), [])

    def test_payload(self):
        payload = call(None, kind='payload', route_name='dsym-files', hints=['symbolicator sources'])
        self.assertEqual(
            summary(links(payload)),
            [('symbolicator', 'sentry', '/api/0/projects/{o}/{p}/files/dsyms', Status.INFERRED)],
        )
        self.assertEqual(summary(links(call(None, kind='payload', route_name='nope', hints=['symbolicator']))), [])

    def test_tests_skipped_unless_asked(self):
        c = call('/{d}/snql', 'POST', ['snuba'], test=True)
        self.assertEqual(links(c), [])
        self.assertEqual(len(links(c, include_tests=True)), 1)

    def test_pathless_request_ignored(self):
        self.assertEqual(links(call(None, hints=['snuba'])), [])


if __name__ == '__main__':
    unittest.main()
