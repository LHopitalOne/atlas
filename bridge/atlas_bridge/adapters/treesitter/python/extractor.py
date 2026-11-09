"""PythonExtractor: HTTP routes and requests in Python code.

Routes: Flask/FastAPI-style decorators (`@app.route`, `@router.get`, blueprints and routers with prefixes) and Django
URLconfs (`path` / `re_path` / `url` lists composed through `include` from the root URLconf).
Requests: verb calls on requests/httpx/aiohttp/session/client-like receivers, `.request(method, url)`, urllib3
`.urlopen(METHOD, path)` and `urllib.request.urlopen`. URLs are resolved through literals, f-strings, `.format`, `%`,
`+`, `urljoin`, local variables and module constants, and through the parameters of wrapper functions up to the
callers that supply them. Payloads: `reverse('route-name')` URLs handed to another service. Service URLs:
module-level names bound to absolute URLs (settings).
"""

from ....core.http import Extraction
from ..kit import LanguageExtractor
from .calls import PayloadCalls, RequestCalls
from .config import SettingUrls
from .files import SlashedFiles
from .policy import PythonTestPolicy
from .routes import DecoratorRoutes, DjangoRoutes, Registrations, UrlRuleRoutes
from .workspace import PythonWorkspace


class PythonExtractor(LanguageExtractor):
    """Python files: one workspace, the route collectors (decorators, URL rules, Django) and the call collectors."""

    GRAMMARS = frozenset({'python'})
    POLICY = PythonTestPolicy
    PREFIXED = (DecoratorRoutes, UrlRuleRoutes)  # share one read of the blueprint and router registrations
    OTHERS = (DjangoRoutes, RequestCalls, PayloadCalls, SettingUrls)

    def workspace(self, repo, sources):
        return PythonWorkspace(repo, sources)

    def collectors(self, workspace):
        registrations = Registrations(workspace)
        prefixed = [collector(workspace, registrations) for collector in self.PREFIXED]
        return prefixed + [collector(workspace) for collector in self.OTHERS]

    def extract(self, repo, files, paths) -> Extraction:
        """The kit's extraction over '/'-separated paths, with routes made unique and sorted."""
        slashed = SlashedFiles(files, paths)
        found = super().extract(repo, slashed, slashed.listed())
        return Extraction(routes=self.unique_routes(found.routes), calls=found.calls, urls=found.urls)

    @staticmethod
    def unique_routes(routes):
        """One route per (file, line, path, methods, name), the first found, sorted by file, line and path."""
        seen, out = set(), []
        for r in routes:
            key = (r.file, r.line, str(r.path), r.methods, r.name)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return sorted(out, key=lambda r: (r.file, r.line, str(r.path)))
