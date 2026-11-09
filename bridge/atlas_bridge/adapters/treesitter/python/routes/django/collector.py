"""DjangoRoutes: URLconfs composed from the root URLconf (or, without one, from every module nothing includes)."""

from ......core.http import Extraction
from ....kit import RouteCollector
from ...scope import Scope
from ...values import PythonValueResolver
from .compose import UrlComposer
from .entries import UrlEntries
from .lists import UrlLists
from .plugins import PluginMounts
from .routers import DrfRouters
from .views import ViewMethods


class DjangoRoutes(RouteCollector):
    """`ROOT_URLCONF = 'proj.urls'` in a settings module names the root (production settings win over test ones).
    Without one, every module with `urlpatterns` that no other such module includes is a root. Plugin apps
    (PluginMounts) add their URLconfs at the prefix their `plugin_app` names."""

    framework = 'django'
    ROOT_SETTING = 'ROOT_URLCONF'
    PATTERNS = 'urlpatterns'

    def __init__(self, workspace):
        super().__init__(workspace)
        self._values = PythonValueResolver(workspace)
        self._lists = UrlLists()
        routers = DrfRouters(workspace, self._values)
        entries = UrlEntries(workspace, self._values, self._lists, routers)
        views = ViewMethods(workspace)
        self._composer = UrlComposer(self.route, workspace.names, self._values, entries, views, routers)
        self._plugins = PluginMounts(workspace, self._values)

    def collect(self) -> Extraction:
        roots = self._roots()
        if roots:
            routes = [r for root in roots for r in self._composer.compose(root, self.PATTERNS).routes]
        else:
            routes = self._unincluded()
        for module_file, regex in self._plugins.mounts():
            routes += self._composer.compose_mounted(module_file, regex).routes
        return Extraction(routes=routes)

    def _roots(self):
        """The modules ROOT_URLCONF names, from the settings least likely to be test settings. Every module-level
        assignment counts: `if RUNNING_X: ROOT_URLCONF = 'proj.x_urls'` names a root of another process."""
        roots = []
        for source in self.workspace.sources:
            if not source.mentions(self.ROOT_SETTING.encode()):
                continue
            for _, value in self.workspace.names.table(source).assignments(self.ROOT_SETTING):
                if value is not None and value.type == 'string':
                    dotted = self._values.string(value, Scope.module(source)).text
                    module_file = self.workspace.names.dotted_module(dotted)
                    if module_file is not None:
                        roots.append((source.test, module_file))
        if not roots:
            return []
        best = min(t for t, _ in roots)
        return list(dict.fromkeys(module_file for t, module_file in roots if t == best))

    def _unincluded(self):
        """Routes of every URLconf module that no other URLconf module includes."""
        needle = self.PATTERNS.encode()
        candidates = [
            s for s in self.workspace.sources if s.mentions(needle) and self.PATTERNS in self._lists.lists_in(s)
        ]
        included, found = set(), {}
        for source in candidates:
            out = self._composer.compose(source, self.PATTERNS)
            found[source.path] = out.routes
            included |= out.included - {source.path}
        return [r for path, routes in found.items() if path not in included for r in routes]
