import unittest

from .support import call, extract, requests_

SETTINGS = """
import os
from dataclasses import dataclass, field

FEED_BASE = 'https://feeds.example.org/v2'


@dataclass(frozen=True)
class Settings:
    feed_base: str = field(default_factory=lambda: os.getenv('FEED_BASE', FEED_BASE))
    billing_url: str = 'http://127.0.0.1:7100'


@dataclass(frozen=True)
class Env:
    mailer_url: str

    @classmethod
    def load(cls) -> 'Env':
        return cls(mailer_url=os.environ.get('MAILER_URL', 'https://relay.example.org/send'))
"""
CLIENTS = """
import aiohttp
import httpx

from app.settings import Settings


class FeedClient:
    def __init__(self, base_url: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=5)

    async def top(self):
        return await self._http.get('/top.json')

    async def item(self, item_id):
        return await self._http.get(f'/items/{item_id}.json')

    async def elsewhere(self):
        return await self._http.get('https://other.example.org/x')


class Billing:
    def __init__(self, settings: Settings) -> None:
        self._session = aiohttp.ClientSession(settings.billing_url)

    async def charge(self):
        return await self._session.post('/charges')


class Mailer:
    def __init__(self, url: str) -> None:
        self._url = url

    def send(self, body):
        return httpx.post(self._url, json=body)
"""
MAIN = """
from app.clients import Billing, FeedClient, Mailer
from app.settings import Env, Settings

settings = Settings()
feed = FeedClient(settings.feed_base)
billing = Billing(settings)
mailer = Mailer(Env.load().mailer_url)
"""


class ClientBaseTest(unittest.TestCase):
    def setUp(self):
        self.ex = extract({'app/settings.py': SETTINGS, 'app/clients.py': CLIENTS, 'app/main.py': MAIN})

    def test_a_relative_url_is_joined_to_the_base_the_client_was_made_with(self):
        found = requests_(self.ex)
        self.assertIn(('GET', '/v2/top.json'), found)
        self.assertIn(('GET', '/v2/items/{item_id}.json'), found)
        self.assertEqual(call(self.ex, '/v2/top.json').host, 'feeds.example.org')
        self.assertIn('settings.feed_base', call(self.ex, '/v2/top.json').hints)  # what the caller passes

    def test_an_absolute_url_ignores_the_base(self):
        self.assertEqual(call(self.ex, '/x').host, 'other.example.org')

    def test_a_positional_base_and_a_settings_field(self):
        self.assertIn('127.0.0.1:7100', call(self.ex, '/charges').hints)

    def test_a_url_held_in_an_attribute_is_read_from_configuration(self):
        mail = call(self.ex, '/send')
        self.assertEqual((mail.method, mail.host), ('POST', 'relay.example.org'))


if __name__ == '__main__':
    unittest.main()
