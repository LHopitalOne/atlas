"""serve: show a written map from a local web server whose Ask panel reaches OpenRouter through it, so the API key
stays on this machine and never reaches the page."""

import functools
import http.server
import json
import os
import threading
import urllib.error
import urllib.request
import webbrowser

from ..core.errors import OutputWriteError
from .command import Command


class LlmProxy(http.server.SimpleHTTPRequestHandler):
    """Serves the map's folder; `/api/llm/ping` says a key is here, `/api/llm/chat/completions` forwards a chat
    request to OpenRouter with OPENROUTER_API_KEY added. Anything else under /api/ is refused."""

    UPSTREAM = 'https://openrouter.ai/api/v1/chat/completions'
    KEY_VARIABLE = 'OPENROUTER_API_KEY'
    PREFIX = '/api/llm/'
    MAX_BODY = 4_000_000  # bytes: a conversation with tool results, never a whole repository
    TIMEOUT = 120

    def do_GET(self):  # noqa: N802 (the name http.server calls)
        if self.path.startswith(self.PREFIX):
            ok = self.path == self.PREFIX + 'ping' and bool(os.environ.get(self.KEY_VARIABLE))
            return self._json(200 if ok else 404, {'ok': ok})
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        key = os.environ.get(self.KEY_VARIABLE, '')
        if self.path != self.PREFIX + 'chat/completions' or not key:
            return self._json(404, {'error': 'not here'})
        size = int(self.headers.get('Content-Length') or 0)
        if size <= 0 or size > self.MAX_BODY:
            return self._json(413, {'error': 'request too large'})
        body = self.rfile.read(size)
        request = urllib.request.Request(
            self.UPSTREAM,
            data=body,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'X-Title': 'Atlas'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT) as r:
                return self._send(r.status, r.read())
        except urllib.error.HTTPError as e:
            return self._send(e.code, e.read())
        except (urllib.error.URLError, TimeoutError) as e:
            return self._json(502, {'error': str(e)})

    def _json(self, status, data):
        self._send(status, json.dumps(data).encode())

    def _send(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass  # quiet: the terminal shows what serve says, not every request


class MapServer:
    """Serves one folder on 127.0.0.1 only, and opens the page in a browser."""

    HOST = '127.0.0.1'

    def __init__(self, folder: str, port: int = 0):
        handler = functools.partial(LlmProxy, directory=folder)
        try:
            self._server = http.server.ThreadingHTTPServer((self.HOST, port), handler)
        except OSError as e:
            raise OutputWriteError(f'{self.HOST}:{port}', e.strerror or str(e)) from e

    @property
    def url(self):
        return f'http://{self.HOST}:{self._server.server_address[1]}'

    def run(self, page: str, open_browser: bool = True, report=print):
        has_key = bool(os.environ.get(LlmProxy.KEY_VARIABLE))
        chat = 'Ask uses OPENROUTER_API_KEY through this server' if has_key else 'no OPENROUTER_API_KEY: Ask is off'
        report(f'atlas: serving {self.url}/{page} ({chat}); Ctrl+C to stop')
        if open_browser:
            threading.Timer(0.3, webbrowser.open, (f'{self.url}/{page}',)).start()
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            report('atlas: stopped')
        finally:
            self._server.server_close()


class ServeCommand(Command):
    name = 'serve'
    help = 'show a map folder (atlas-out) from a local server, with Ask reaching OpenRouter through it'

    def configure(self, parser):
        parser.add_argument(
            'folder', nargs='?', default='atlas-out', help='the folder atlas wrote (default: atlas-out)'
        )
        parser.add_argument('--port', type=int, default=8780, help='port on 127.0.0.1 (default: 8780; 0 picks one)')
        parser.add_argument('--no-open', action='store_true', help='do not open a browser')

    def run(self, args):
        MapServer(os.path.abspath(args.folder), args.port).run('atlas.html', not args.no_open, self.report)
