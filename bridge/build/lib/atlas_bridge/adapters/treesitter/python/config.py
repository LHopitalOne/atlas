"""SettingUrls: module-level names bound to absolute URLs, the service addresses a settings module configures."""

from ....core.addresses import ServiceUrl
from ....core.http import Extraction
from ..kit import Collector
from .scope import Scope
from .syntax import PythonSyntax
from .values import Marker, PythonValueResolver, UrlShape


class SettingUrls(Collector):
    """`COURSE_CATALOG_API_URL = f'{COURSE_CATALOG_URL_ROOT}/api/v1'` with `COURSE_CATALOG_URL_ROOT =
    'http://edx.devstack.discovery:18381'`, and `'ISSUER': 'http://localhost:18000/oauth2'` in a module-level dict.
    Only names that read like URLs (or values written as URLs) are resolved; test code and test settings are left
    out."""

    SCHEME = '://'
    TEST_MODULES = frozenset({'test.py', 'testing.py', 'test_settings.py'})

    def __init__(self, workspace):
        super().__init__(workspace)
        self._values = PythonValueResolver(workspace)

    def collect(self) -> Extraction:
        urls = []
        for source in self.workspace.sources:
            if source.test or source.path.rsplit('/', 1)[-1] in self.TEST_MODULES:
                continue
            for st in PythonSyntax.module_statements(source.root):
                for e in st.named_children if st.type == 'expression_statement' else ():
                    urls += self._assignment(source, e)
        return Extraction(urls=urls)

    def _assignment(self, source, e):
        if e.type != 'assignment' or e.child_by_field_name('left').type != 'identifier':
            return []
        right = e.child_by_field_name('right')
        if right is None:
            return []
        name = PythonSyntax.text(e.child_by_field_name('left'))
        if right.type == 'dictionary':
            return [u for p in right.named_children if p.type == 'pair' for u in self._pair(source, p)]
        return self._named(source, name, right)

    def _pair(self, source, pair):
        key = pair.child_by_field_name('key')
        if key is None or key.type != 'string':
            return []
        name = self._values.string(key, Scope.module(source)).text
        return self._named(source, name, pair.child_by_field_name('value'))

    def _named(self, source, name, node):
        if node is None or not (UrlShape.URLISH.search(name) or self.SCHEME.encode() in node.text):
            return []
        out = []
        for v in self._values.resolve(node, Scope.module(source)):
            text = Marker.braces(v.text)
            url = ServiceUrl.parse(self.workspace.repo, source.path, PythonSyntax.line(node), name, text)
            if v.is_literal and url is not None and '{' not in url.host:
                out.append(url)
        return out
