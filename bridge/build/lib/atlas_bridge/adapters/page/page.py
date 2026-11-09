"""The Atlas page (built once with `npm run build:page`, shipped inside this package) with a graph spec in it.

The template is dist/atlas-offline.html built with a placeholder for the embedded graph. Filling the placeholder
gives the same file `node scripts/build.mjs --offline --graph=spec.json` would write, without Node.js.
"""

import json
import os

from ...core.errors import PageTemplateError


class AtlasPage:
    TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'atlas.html')
    MARKER = '__ATLAS_SPEC__'
    SLOT = f'<script type="application/json" id="selfGraph">{MARKER}</script>'

    def __init__(self, template: str = TEMPLATE):
        self._template = template

    def render(self, spec: dict) -> str:
        html = self._read()
        # '<' only occurs inside JSON strings, where < is the same character; the script element cannot end early
        data = json.dumps(spec, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
        head, _, tail = html.partition(self.SLOT)
        return f'{head}<script type="application/json" id="selfGraph">{data}</script>{tail}'

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
        if self.SLOT not in html:
            raise PageTemplateError(self._template)
        return html
