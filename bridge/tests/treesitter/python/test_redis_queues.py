import unittest

from atlas_bridge.core.http import Protocol

from .support import extract

R = Protocol.REDIS


class RedisListsAndStreamsTest(unittest.TestCase):
    def test_lists_and_streams_through_settings_and_constructor_arguments(self):
        ex = extract(
            {
                'app/settings.py': """
                import os
                from dataclasses import dataclass, field

                @dataclass(frozen=True)
                class Settings:
                    jobs: str = field(default_factory=lambda: os.getenv('JOBS_LIST', 'mail:jobs'))
                    events: str = 'mail.events'
                """,
                'app/queue.py': """
                from redis.asyncio import Redis

                from app.settings import Settings

                class Jobs:
                    def __init__(self, redis: Redis, settings: Settings) -> None:
                        self._redis = redis
                        self._list = settings.jobs
                        self._stream = settings.events

                    async def push(self, job):
                        await self._redis.lpush(self._list, job)

                    async def record(self, fields):
                        await self._redis.xadd(self._stream, fields)
                """,
                'app/worker.py': """
                import redis

                r = redis.Redis()

                def work():
                    r.brpop(['mail:retries', 'mail:urgent'], timeout=5)
                    r.xreadgroup('workers', 'w1', {'audit.log': '>'}, count=10)
                    r.xread(streams={'audit.trail': '$'})
                    r.lmove('mail:inbox', 'mail:busy')
                """,
            }
        )
        sends = {(c.protocol, str(c.path)) for c in ex.calls if c.protocol == R}
        receives = {(r.protocol, str(r.path)) for r in ex.routes if r.protocol == R}
        self.assertEqual(sends, {(R, '/mail:jobs'), (R, '/mail.events')})
        self.assertEqual(
            receives,
            {(R, '/mail:retries'), (R, '/mail:urgent'), (R, '/audit.log'), (R, '/audit.trail'), (R, '/mail:inbox')},
        )


if __name__ == '__main__':
    unittest.main()
