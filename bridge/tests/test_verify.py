import unittest

from atlas_bridge.core.evidence import Assumption, Verdict, Verification
from atlas_bridge.core.http import Call, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.link import Link
from atlas_bridge.usecases.ports import DefinitionOracle
from atlas_bridge.usecases.verify import LinkVerifier

GOOD = Assumption('c.py', 1, 'pool', 'p.py', 1, 2)
BAD = Assumption('c.py', 2, 'pool', 'p.py', 1, 2)
VAGUE = Assumption('c.py', 3, 'pool')
ROUTE = Route('api', 'v.py', 1, PathTemplate.parse('/x'))


class FakeOracle(DefinitionOracle):
    ANSWERS = {GOOD: Verdict.CONFIRMED, BAD: Verdict.CONTRADICTED, VAGUE: Verdict.UNKNOWN}

    def covers(self, repo):
        return repo == 'web'

    def check(self, repo, assumption):
        return self.ANSWERS[assumption]


def link(*assumptions, status=Status.MATCHED, repo='web', **kw):
    call = Call(repo, 'c.py', 1, PathTemplate.parse('/x'), assumptions=assumptions, **kw)
    return Link(call, repo, 'api', ROUTE, status, 'r')


class LinkVerifierTest(unittest.TestCase):
    def verify(self, *links):
        return [lk.verification for lk in LinkVerifier(FakeOracle()).verify(list(links))]

    def test_verifications(self):
        self.assertEqual(
            self.verify(link(GOOD), link(GOOD, BAD), link(GOOD, VAGUE), link()),
            [Verification.CONFIRMED, Verification.CONTRADICTED, Verification.UNVERIFIED, Verification.SYNTAX],
        )

    def test_only_matched_links_of_indexed_repos_are_checked(self):
        self.assertEqual(
            self.verify(link(GOOD, status=Status.INFERRED), link(GOOD, repo='other'), link(kind=Call.PAYLOAD)),
            [Verification.UNVERIFIED] * 3,
        )

    def test_verdicts_and_counts(self):
        checked = LinkVerifier(FakeOracle()).verify([link(GOOD, BAD), link()])
        self.assertEqual(checked[0].verdicts, ((GOOD, Verdict.CONFIRMED), (BAD, Verdict.CONTRADICTED)))
        counts = LinkVerifier.count(checked)
        self.assertEqual((counts['contradicted'], counts['syntax'], counts['confirmed']), (1, 1, 0))
        self.assertEqual((counts['assumptions_confirmed'], counts['assumptions_contradicted']), (1, 1))

    def test_assumption_coverage(self):
        self.assertTrue(GOOD.covers('p.py', 2))
        self.assertFalse(GOOD.covers('p.py', 3))
        self.assertFalse(GOOD.covers('q.py', 1))
        self.assertTrue(VAGUE.covers('anything.py', 99))


if __name__ == '__main__':
    unittest.main()
