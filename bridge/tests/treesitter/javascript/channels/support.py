"""The channels (not HTTP) a temporary repository of javascript / typescript files sends and receives on."""

from atlas_bridge.core.http import Protocol

from ..support import Repository


class Channels:
    """What JavaScriptExtractor finds in {path: source}, other than HTTP, as comparable tuples."""

    def __init__(self, files, repo='web'):
        self.extraction = Repository(files, repo).extract()

    @classmethod
    def of(cls, source, path='src/a.js'):
        return cls({path: source})

    @property
    def calls(self):
        """[(protocol, method, path, file, line)] in the order found."""
        return [
            (c.protocol, c.method, str(c.path), c.file, c.line)
            for c in self.extraction.calls
            if c.protocol != Protocol.HTTP
        ]

    @property
    def routes(self):
        """[(protocol, sorted methods, path, file, line)] in the order found."""
        return [
            (r.protocol, sorted(r.methods), str(r.path), r.file, r.line)
            for r in self.extraction.routes
            if r.protocol != Protocol.HTTP
        ]

    def call(self, path):
        """The first channel call to `path`."""
        return next(c for c in self.extraction.calls if c.protocol != Protocol.HTTP and str(c.path) == path)
