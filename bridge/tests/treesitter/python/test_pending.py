import unittest

from atlas_bridge.adapters.treesitter.python.calls import Evidence, PendingRequest, Reading, RequestRun
from atlas_bridge.adapters.treesitter.python.values import Marker


class RequestRunTest(unittest.TestCase):
    def test_settle_budget_is_owned_by_the_run(self):
        run = RequestRun(client=True)
        spent = [run.spend() for _ in range(RequestRun.MAX_SETTLES + 2)]
        self.assertTrue(all(spent[: RequestRun.MAX_SETTLES]))
        self.assertEqual(spent[RequestRun.MAX_SETTLES :], [False, False])

    def test_first_visit_checks_and_records(self):
        run = RequestRun(client=False)
        self.assertTrue(run.first_visit(('w', 'a')))
        self.assertFalse(run.first_visit(('w', 'a')))
        self.assertTrue(run.first_visit(('w', 'b')))

    def test_state_is_private(self):
        run = RequestRun(client=True)
        self.assertTrue(run.client)
        with self.assertRaises(AttributeError):
            run.client = False
        with self.assertRaises(AttributeError):
            run.seen = set()


class PendingRequestTest(unittest.TestCase):
    def test_forwarded_goes_one_level_up(self):
        start = PendingRequest(Marker.wrap('p'), 'GET', frozenset({'h'}))
        up = start.forwarded('/x', 'POST', frozenset({'h', 'i'}), ('f.py', 1))
        self.assertEqual((up.url, up.method, up.depth, up.stack), ('/x', 'POST', 1, frozenset({('f.py', 1)})))
        self.assertIs(up.evidence, start.evidence)
        self.assertEqual(start.depth, 0)  # immutable: the original is unchanged
        self.assertEqual(up.visit('w'), ('w', '/x', 'POST', Evidence()))

    def test_says_more_at_the_request_and_at_callers(self):
        lit = Reading.from_request('/a/' + Marker.wrap('p'), 'GET', client=True)
        self.assertTrue(lit.open and lit.literals == 1 and lit.pathlike)
        self.assertTrue(PendingRequest('', 'GET', frozenset()).says_more(lit))
        caller = PendingRequest('', 'GET', frozenset(), depth=1, evidence=Evidence(literals=1))
        self.assertFalse(caller.says_more(lit))  # no more literals than below
        two = Reading.from_request('/a/b', 'GET', client=True)
        self.assertTrue(caller.says_more(two))
        method_settled = PendingRequest('', 'GET', frozenset(), 1, Evidence(1, method_open=True))
        self.assertTrue(method_settled.says_more(lit))
        with_base = Reading.from_request('http://api/a', 'GET', client=True)
        self.assertTrue(caller.says_more(with_base))

    def test_evidence_accumulates(self):
        reading = Reading.from_request('http://api/a/b', Marker.choice(0), client=True)
        seen = PendingRequest('', 'GET', frozenset()).seen_with(reading)
        self.assertEqual(seen.evidence, Evidence(2, True, frozenset({'api'})))
        self.assertEqual(seen.evidence.then(Reading.from_request('/a', 'GET', True)).literals, 2)
