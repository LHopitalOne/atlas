import unittest

from .support import call, extract, requests_


class HttpxBaseUrlTest(unittest.TestCase):
    def test_a_relative_url_is_appended_to_the_base_path_of_an_attribute_client(self):
        ex = extract(
            {
                'billing/api.py': """
                import httpx

                class Ledger:
                    def __init__(self, root):
                        self._http = httpx.Client(base_url=f'{root}/api/v2/', timeout=3)

                    def entries(self, account):
                        return self._http.get(f'/accounts/{account}/entries')

                    def post(self, entry):
                        return self._http.post('entries', json=entry)

                    def absolute(self):
                        return self._http.get('https://status.example.org/ping')
                """
            }
        )
        self.assertEqual(
            requests_(ex),
            {
                ('GET', '/api/v2/accounts/{account}/entries'),
                ('POST', '/api/v2/entries'),
                ('GET', '/ping'),
            },
        )
        self.assertIn('root', call(ex, '/api/v2/entries').hints)

    def test_module_and_local_async_clients(self):
        ex = extract(
            {
                'jobs/sync.py': """
                from httpx import AsyncClient, Client

                CATALOG = Client(base_url='http://catalog:8000/v1')

                def products():
                    return CATALOG.get('/products')

                async def stock():
                    client = AsyncClient(base_url='http://stock:9000/internal')
                    return await client.get('/levels')
                """
            }
        )
        self.assertEqual(requests_(ex), {('GET', '/v1/products'), ('GET', '/internal/levels')})

    def test_other_clients_keep_the_url_as_written(self):
        ex = extract(
            {
                'jobs/plain.py': """
                import requests
                from vendor import Client

                session = requests.Session()
                other = Client(base_url='http://x/root')

                def a():
                    return session.get('/health/live')

                def b():
                    return other.get('/health/ready')
                """
            }
        )
        self.assertEqual(requests_(ex), {('GET', '/health/live'), ('GET', '/health/ready')})


if __name__ == '__main__':
    unittest.main()
