import unittest

from atlas_bridge.core.http import Call, PathTemplate, Protocol, Route
from atlas_bridge.usecases.mentions import NamedChannels
from atlas_bridge.usecases.ports import ChannelMentions

P = PathTemplate.parse


class FakeMentions(ChannelMentions):
    def __init__(self, found):
        self.found = found  # {(repo, name): [(file, line, around)]}

    def mentions(self, repo, name):
        return self.found.get((repo, name), [])


def send(repo, topic, protocol=Protocol.KAFKA, **kw):
    return Call(repo, 'producer.py', 1, P(f'/{topic}'), protocol=protocol, **kw)


class NamedChannelsTest(unittest.TestCase):
    def routes(self, calls, found, routes=()):
        named = NamedChannels(FakeMentions(found), ['api', 'storage', 'edge'])
        return [(r.repo, r.file, r.line, str(r.path), r.protocol) for r in named.routes(calls, list(routes))]

    def test_a_reader_naming_a_topic_another_repository_sends_to(self):
        found = {
            ('storage', 'orders'): [
                ('docs/notes.py', 3, 'print("orders")'),  # no reader's words around it
                ('storage/orders.yaml', 7, 'stream_loader:\n  default_topic: orders'),
            ],
            ('edge', 'orders'): [('edge/config.rs', 9, 'producer topics: "orders"')],  # a writer's settings
        }
        self.assertEqual(
            self.routes([send('api', 'orders')], found), [('storage', 'storage/orders.yaml', 7, '/orders', 'kafka')]
        )

    def test_what_gets_no_named_receiver(self):
        found = {('storage', 'orders'): [('consumer.py', 2, 'consumer.subscribe(["orders"])')]}
        both = [send('api', 'orders'), send('storage', 'orders')]  # it sends to the topic too
        self.assertEqual(self.routes(both, found), [])
        known = [Route('storage', 'consumer.py', 2, P('/orders'), protocol=Protocol.KAFKA)]
        self.assertEqual(self.routes([send('api', 'orders')], found, known), [])  # already read from code
        self.assertEqual(self.routes([send('api', 'orders', test=True)], found), [])
        self.assertEqual(self.routes([send('api', 'orders', protocol=Protocol.HTTP)], found), [])  # not a broker


if __name__ == '__main__':
    unittest.main()
