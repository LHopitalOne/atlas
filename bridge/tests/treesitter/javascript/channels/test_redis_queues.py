import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import Channels

R = Protocol.REDIS
CONFIG = """
export function loadSettings(env = process.env) {
  return {
    events: env.EVENTS_STREAM ?? 'shop.events',
    jobs: env.JOBS_LIST ?? 'shop:jobs',
  };
}
"""
CONSUMER = """
import Redis from 'ioredis';

export class Consumer {
  constructor(private readonly settings) {
    this.redis = new Redis();
  }

  async run() {
    await this.redis.xreadgroup('GROUP', 'g', 'c1', 'COUNT', 10, 'BLOCK', 500, 'STREAMS', this.settings.events, '>');
    await this.redis.brpop(this.settings.jobs, 5);
    await this.redis.xread('BLOCK', 0, 'STREAMS', 'a.stream', 'b.stream', '$', '$');
  }
}
"""
MAIN = """
import { loadSettings } from './settings';
import { Consumer } from './consumer';

const settings = loadSettings();
new Consumer(settings).run();
"""
NODE_REDIS = """
const { createClient } = require('redis');
async function main(client) {
  await client.lPush('mail:jobs', 'x');
  await client.xAdd('mail.events', '*', { a: '1' });
  await client.xReadGroup('g', 'c', { key: 'mail.audit', id: '>' });
}
"""


class RedisListsAndStreamsTest(unittest.TestCase):
    def test_streams_read_after_the_streams_token_and_keys_from_a_config_function(self):
        found = Channels({'src/settings.ts': CONFIG, 'src/consumer.ts': CONSUMER, 'src/main.ts': MAIN})
        routes = {(p, path) for p, _, path, _, _ in found.routes}
        self.assertEqual(routes, {(R, '/shop.events'), (R, '/shop:jobs'), (R, '/a.stream'), (R, '/b.stream')})

    def test_node_redis_spellings(self):
        found = Channels.of(NODE_REDIS)
        self.assertEqual(
            {(p, m, path) for p, m, path, _, _ in found.calls}, {(R, ANY, '/mail:jobs'), (R, ANY, '/mail.events')}
        )
        self.assertEqual({(p, path) for p, _, path, _, _ in found.routes}, {(R, '/mail.audit')})


if __name__ == '__main__':
    unittest.main()
