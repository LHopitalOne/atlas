"""JavaScriptWorkspace: the javascript / typescript files of a repository, and which of them are worth reading."""

from ..kit import SourceFile, Workspace
from .clients.registry import ClientRegistry
from .module import JsModule
from .policy import JavaScriptTestPolicy
from .source import JsSource


class JavaScriptWorkspace(Workspace):
    """Index: the files worth scanning. Each pass over them reads every file with a new JsModule (FilePass), and the
    test policy decides which code is test code."""

    # bytes a file must contain to declare a route or send a request (checked before parsing)
    PRECHECK = (
        b'fetch',
        b'axios',
        b'got(',
        b'ky(',
        b'.get(',
        b'.post(',
        b'.put(',
        b'.delete(',
        b'.del(',
        b'.patch(',
        b'.head(',
        b'.options(',
        b'.all(',
        b'.route(',
        b'.request(',
        b'.requestPromise(',
        b'.use(',
    )

    POLICY = JavaScriptTestPolicy  # used when the workspace is not given the extractor's policy

    def __init__(self, repo: str, sources: list[SourceFile], policy: JavaScriptTestPolicy | None = None):
        self._policy = policy if policy is not None else self.POLICY()
        super().__init__(repo, [JsSource.adopt(s) for s in sources])

    def index(self):
        self._scanned = [
            s for s in self.sources if s.mentions(*ClientRegistry.BASE_BYTES) or s.mentions(*self.PRECHECK)
        ]

    def scanned(self) -> list[JsSource]:
        """Files that may declare routes, send requests or define a client class, in path order."""
        return self._scanned

    def modules(self):
        """A new JsModule for each scanned file, in path order, made as the caller gets to it."""
        return (self.module(s) for s in self._scanned)

    @staticmethod
    def module(source: JsSource) -> JsModule:
        """A new reading of a file, with caches of its own."""
        return JsModule(source)

    def is_test(self, source: SourceFile, node=None) -> bool:
        return source.test or (node is not None and self._policy.in_test_block(node))
