import unittest

from atlas_bridge.core.http import Call, Extraction, PathTemplate, Protocol, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.channels import OwnChannelRule
from atlas_bridge.usecases.link import LinkFinder

P = PathTemplate.parse
TASK = Protocol.TASK
RULES = (*LinkFinder.RULES[:-1], OwnChannelRule, LinkFinder.RULES[-1])


def links(calls, routes):
    found = LinkFinder(['app', 'other'], rules=RULES).find(Extraction(list(routes), list(calls)))
    return [(lk.target, str(lk.route.path) if lk.route else None, lk.status) for lk in found]


def task(path, repo='app'):
    return Call(repo, 'views.py', 1, P(path), protocol=TASK)


class OwnChannelTest(unittest.TestCase):
    def test_a_task_its_own_repository_defines(self):
        routes = [Route('app', 'tasks.py', 3, P('/app.tasks.send_mail'), protocol=TASK)]
        self.assertEqual(
            links([task('/app.tasks.send_mail')], routes), [('app', '/app.tasks.send_mail', Status.MATCHED)]
        )

    def test_a_worker_that_takes_every_job_of_its_queue(self):
        routes = [Route('app', 'worker.ts', 9, P('/emails/{job}'), protocol=TASK)]
        self.assertEqual(links([task('/emails/welcome')], routes), [('app', '/emails/{job}', Status.MATCHED)])
        self.assertEqual(
            links([task('/emails/welcome')], [Route('app', 'w.ts', 1, P('/{name}/{job}'), protocol=TASK)]), []
        )

    def test_what_it_leaves_to_other_rules(self):
        mine = Route('app', 'tasks.py', 3, P('/app.tasks.send_mail'), protocol=TASK)
        theirs = Route('other', 'tasks.py', 3, P('/app.tasks.send_mail'), protocol=TASK)
        found = links([task('/app.tasks.send_mail')], [mine, theirs])
        self.assertNotIn(('app', '/app.tasks.send_mail', Status.MATCHED), found)  # another repository serves it
        http = Call('app', 'views.py', 1, P('/orders/new'))
        self.assertEqual(links([http], [Route('app', 'urls.py', 1, P('/orders/new'))]), [])  # HTTP is not a channel


if __name__ == '__main__':
    unittest.main()
