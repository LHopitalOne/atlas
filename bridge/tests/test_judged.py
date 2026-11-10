"""Requests the rules leave open, settled by a route judge (usecases/judged.py), and what Jev is asked and how its
answer is read (adapters/jev/question.py). The judge here is a stand-in: no request leaves the machine."""

import os
import tempfile
import unittest
import unittest.mock

from atlas_bridge.adapters.atlas import LinkFile
from atlas_bridge.adapters.jev import JevRouteJudge, RouteQuestion
from atlas_bridge.core.errors import JudgeUnavailableError
from atlas_bridge.core.evidence import Verification
from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.judged import JudgedLinks
from atlas_bridge.usecases.link import Link
from atlas_bridge.usecases.ports import Choice, JudgeCase, RouteJudge

P = PathTemplate.parse
PLAN = Route('api', 'billing/urls.py', 10, P('/json/billing/plan'), frozenset({'PATCH'}), 'update_plan')
SEATS = Route('api', 'billing/urls.py', 11, P('/json/billing/seats'), frozenset({'PATCH'}), 'update_seats')
CALL = Call('web', 'src/billing.ts', 5, P('/json/{*base}/billing/plan'), 'PATCH', 'changePlan')


class Pick(RouteJudge):
    """Answers every case with the candidate whose path is `path`, at `p`; records what it was asked."""

    def __init__(self, path, p=0.95):
        self.path, self.p, self.asked = path, p, []

    def choose(self, cases):
        self.asked += cases
        out = []
        for case in cases:
            paths = [str(r.path) for r in case.candidates]
            out.append(Choice(paths.index(self.path), self.p) if self.path in paths else Choice(None, 0.6))
        return out


def refine(judge, links=(), calls=(CALL,), within=False):
    return JudgedLinks(judge, within=within).refine(list(links), Extraction([PLAN, SEATS], list(calls)))


class JudgedLinksTest(unittest.TestCase):
    def test_an_open_request_gets_the_route_the_judge_is_sure_of(self):
        judge = Pick('/json/billing/plan')
        (link,) = refine(judge)
        self.assertEqual((link.route, link.status, link.verification), (PLAN, Status.INFERRED, Verification.JUDGED))
        self.assertIn('p=0.95', link.reason)
        self.assertEqual(
            [str(r.path) for r in judge.asked[0].candidates], ['/json/billing/plan', '/json/billing/seats']
        )

    def test_an_unsure_pick_or_none_keeps_what_the_rules_said(self):
        self.assertEqual(refine(Pick('/json/billing/plan', p=0.6)), [])
        unmatched = Link(CALL, 'web', 'api', None, Status.UNMATCHED, 'two routes fit')
        self.assertEqual(refine(Pick('/nowhere'), [unmatched]), [unmatched])

    def test_settled_requests_are_never_asked(self):
        matched = Link(CALL, 'web', 'api', SEATS, Status.MATCHED, 'named target')
        judge = Pick('/json/billing/plan')
        self.assertEqual(refine(judge, [matched]), [matched])
        self.assertEqual(judge.asked, [])

    def test_its_own_repositorys_routes_only_with_within(self):
        own = Call('api', 'web/billing.ts', 5, P('/json/{*base}/billing/plan'), 'PATCH')
        judge = Pick('/json/billing/plan')
        self.assertEqual(refine(judge, calls=[own]), [])
        self.assertEqual(judge.asked, [])
        (link,) = refine(judge, calls=[own], within=True)
        self.assertEqual(link.route, PLAN)

    def test_a_request_to_an_outside_host_is_not_asked(self):
        outside = Call('web', 'src/x.ts', 1, P('/billing/plan'), 'PATCH', hints=frozenset({'//api.stripe.com'}))
        judge = Pick('/json/billing/plan')
        refine(judge, calls=[outside])
        self.assertEqual(judge.asked, [])


class RouteQuestionTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, 'src'))
        with open(os.path.join(self.dir, 'src', 'billing.ts'), 'w') as f:
            f.write('\n'.join(f'line {n}' for n in range(1, 12)))
        self.question = RouteQuestion({'web': self.dir})
        self.case = JudgeCase(CALL, (PLAN, SEATS))

    def test_state_shows_the_code_around_the_call_and_the_candidates(self):
        state = self.question.state(self.case)
        self.assertIn('>>    5 line 5', state['request']['code around the call (>> marks its line)'])
        self.assertEqual(sorted(state['candidate routes']), ['r1', 'r2'])
        criteria = self.question.questions(self.case)['route']['criteria']
        self.assertEqual(sorted(criteria), ['none', 'r1', 'r2'])

    def test_answers_are_read_back_as_choices(self):
        pick = {'route': {'choice': 'r2', 'probabilities': {'r1': 0.1, 'r2': 0.9}}}
        self.assertEqual(self.question.choice(self.case, pick), Choice(1, 0.9))
        none = {'route': {'choice': 'none', 'probabilities': {'none': 0.7}}}
        self.assertEqual(self.question.choice(self.case, none).index, None)
        self.assertEqual(self.question.choice(self.case, {}).index, None)

    def test_no_key_is_a_clear_error(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(JudgeUnavailableError):
            JevRouteJudge({})


class JudgedOnTheMapTest(unittest.TestCase):
    def test_a_judged_link_has_its_own_proof(self):
        record = {
            'caller': 'web',
            'target': 'api',
            'status': 'inferred',
            'verification': 'judged',
            'call': {'file': 'src/billing.ts', 'line': 5, 'method': 'PATCH', 'path': '/json/{*base}/billing/plan'},
            'route': {'repo': 'api', 'file': 'billing/urls.py', 'line': 10, 'path': '/json/billing/plan'},
        }
        (parsed,) = LinkFile().parse({'links': [record]})
        self.assertEqual(parsed.proof, 'judged')


if __name__ == '__main__':
    unittest.main()
