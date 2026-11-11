"""The Atlas page (built once with `npm run build:page`, shipped inside this package) with a graph spec in it.

The template is dist/atlas-offline.html built with a placeholder for the embedded graph. Filling the placeholder
gives the same file `node scripts/build.mjs --offline --graph=spec.json` would write, without Node.js.

The page also carries the OpenRouter key Ask Atlas uses, so Ask works by opening the file (like Graphify's
graph.html, nothing to serve). A page written without a key has Ask turned off; anyone holding a page with a key can
use that key.
"""

import json
import os

from ...core.errors import PageTemplateError


class AtlasPage:
    TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'atlas.html')
    MARKER = '__ATLAS_SPEC__'
    SLOT = f'<script type="application/json" id="selfGraph">{MARKER}</script>'
    KEY_SLOT = '<script type="application/json" id="askKey"></script>'

    def __init__(self, template: str = TEMPLATE, key: str | None = None):
        self._template = template
        self._key = key or None

    def render(self, spec: dict) -> str:
        html = self._read()
        key = self._json({'key': self._key})
        html = html.replace(self.KEY_SLOT, f'<script type="application/json" id="askKey">{key}</script>', 1)
        head, _, tail = html.partition(self.SLOT)
        return f'{head}<script type="application/json" id="selfGraph">{self._json(spec)}</script>{tail}'

    @staticmethod
    def _json(data):
        # '<' only occurs inside JSON strings, where \\u003c is the same character; the script element cannot end early
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')

    def write(self, path: str, spec: dict) -> str:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.render(spec))
        return path

    def _read(self):
        try:
            with open(self._template, encoding='utf-8') as f:
                html = f.read()
        except OSError as e:
            raise PageTemplateError(self._template) from e
        if self.SLOT not in html or self.KEY_SLOT not in html:
            raise PageTemplateError(self._template)
        return html
