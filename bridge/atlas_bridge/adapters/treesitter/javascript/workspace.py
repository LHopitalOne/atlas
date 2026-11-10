"""JavaScriptWorkspace: the javascript / typescript files of a repository, and which of them are worth reading."""

from ..kit import SourceFile, Workspace
from .calls.jquery import JQueryRequests
from .calls.libraries import EntryPoints
from .clients.registry import ClientRegistry
from .linker import ModuleLinker
from .module import JsModule
from .policy import JavaScriptTestPolicy
from .source import JsSource


class JavaScriptWorkspace(Workspace):
    """Index: the files worth scanning. Each pass over them reads every file with a new JsModule (FilePass), and the
    test policy decides which code is test code."""

    # bytes a file must contain to declare a route or send a request (checked before parsing); a method call may
    # carry TypeScript type arguments: `http.get<Series>(url)`
    METHODS = ('get', 'post', 'put', 'delete', 'del', 'patch', 'head', 'options', 'all', 'route', 'request')
    METHODS += ('requestPromise', 'use')
    PRECHECK = (b'fetch', b'axios', b'got(', b'ky(') + tuple(f'.{m}{c}'.encode() for m in METHODS for c in '(<')
    PRECHECK += EntryPoints.MENTIONS  # files that import a data fetching or GraphQL library
    PRECHECK += EntryPoints.METHOD_MENTIONS  # files that call a GraphQL client object, maybe made in another file
    PRECHECK += JQueryRequests.MENTIONS  # `$.ajax(`, `$.getJSON(`

    POLICY = JavaScriptTestPolicy  # used when the workspace is not given the extractor's policy

    def __init__(
        self, repo: str, sources: list[SourceFile], policy: JavaScriptTestPolicy | None = None, root: str = ''
    ):
        self._policy = policy if policy is not None else self.POLICY()
        self._root = root
        super().__init__(repo, [JsSource.adopt(s) for s in sources])

    @property
    def root(self) -> str:
        """The repository's folder on disk ('' when the files were not read from one)."""
        return self._root

    def index(self):
        self._scanned = [
            s for s in self.sources if s.mentions(*ClientRegistry.BASE_BYTES) or s.mentions(*self.PRECHECK)
        ]

    def scanned(self) -> list[JsSource]:
        """Files that may declare routes, send requests or define a client class, in path order."""
        return self._scanned

    def modules(self):
        """A new JsModule for each scanned file, in path order, made as the caller gets to it. The modules of one
        call share a linker, so the files they import are read once."""
        linker = self.linker()
        return (self.module(s, linker) for s in self._scanned)

    def linker(self) -> ModuleLinker:
        """A new linker over every file of the repository."""
        return ModuleLinker(self.sources, JsModule)

    @staticmethod
    def module(source: JsSource, linker: ModuleLinker | None = None) -> JsModule:
        """A new reading of a file, with caches of its own."""
        return JsModule(source, linker)

    def is_test(self, source: SourceFile, node=None) -> bool:
        return source.test or (node is not None and self._policy.in_test_block(node))
