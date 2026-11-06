import unittest

from atlas_bridge.core.evidence import Assumption

from .support import call, extract

POOL = """
from urllib3 import connection_from_url

_pool = connection_from_url(settings.SNUBA_URL)
"""


class PythonAssumptionsTest(unittest.TestCase):
    def test_module_client_followed_through_an_import(self):
        ex = extract(
            {
                'svc/pools.py': POOL,
                'svc/query.py': """
            from svc.pools import _pool

            def run():
                return _pool.urlopen('POST', '/snql')
            """,
            }
        )
        self.assertEqual(call(ex, '/snql').assumptions, (Assumption('svc/query.py', 5, '_pool', 'svc/pools.py', 4, 4),))

    def test_class_attribute_client(self):
        ex = extract(
            {
                'svc/client.py': """
            import requests

            class Api:
                def __init__(self):
                    self.session = requests.Session()

                def get(self):
                    return self.session.get('http://api/orders')
            """
            }
        )
        self.assertEqual(
            call(ex, '/orders').assumptions, (Assumption('svc/client.py', 9, 'session', 'svc/client.py', 4, 9),)
        )

    def test_local_client_needs_no_assumption(self):
        ex = extract(
            {
                'svc/local.py': """
            import requests

            def get():
                s = requests.Session()
                return s.get('http://api/orders')
            """
            }
        )
        self.assertEqual(call(ex, '/orders').assumptions, ())

    def test_each_wrapper_hop_is_an_assumption(self):
        ex = extract(
            {
                'svc/wrap.py': """
            import requests

            class Client:
                def _request(self, path):
                    return requests.post('http://api' + path)

                def create(self, path):
                    return self._request(path)

                def orders(self):
                    return self.create('/orders')
            """
            }
        )
        hops = {(a.line, a.name, a.target_start, a.target_end) for a in call(ex, '/orders').assumptions}
        self.assertEqual(hops, {(9, '_request', 5, 6), (12, 'create', 8, 9)})


if __name__ == '__main__':
    unittest.main()
