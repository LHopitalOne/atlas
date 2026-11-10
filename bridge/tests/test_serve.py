"""atlas serve (cli/serve.py): the map's folder on 127.0.0.1, and a proxy that adds the OpenRouter key on the way
out, so the page never holds it. No request leaves the machine here."""

import os
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request

from atlas_bridge.cli.serve import LlmProxy, MapServer


class ServeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'atlas.html'), 'w') as f:
            f.write('<html>map</html>')
        self.server = MapServer(self.dir, 0)
        self.thread = threading.Thread(target=self.server._server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server._server.shutdown()
        self.server._server.server_close()

    def get(self, path, data=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.server.url + path, data=data), timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_serves_the_page_on_localhost_only(self):
        self.assertTrue(self.server.url.startswith('http://127.0.0.1:'))
        self.assertEqual(self.get('/atlas.html'), (200, b'<html>map</html>'))

    def test_ping_says_whether_a_key_is_here(self):
        with unittest.mock.patch.dict(os.environ, {LlmProxy.KEY_VARIABLE: 'sk-test'}):
            self.assertEqual(self.get('/api/llm/ping')[0], 200)
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.get('/api/llm/ping')[0], 404)
            self.assertEqual(self.get('/api/llm/chat/completions', b'{}')[0], 404)  # no key: nothing forwarded

    def test_only_the_chat_path_is_forwarded(self):
        with unittest.mock.patch.dict(os.environ, {LlmProxy.KEY_VARIABLE: 'sk-test'}):
            self.assertEqual(self.get('/api/llm/models', b'{}')[0], 404)
            self.assertEqual(self.get('/api/other')[0], 404)
