"""Requests declared by implementing a request trait: `fn path(&self) -> Cow<str> { "/api/x/".into() }`."""

from ...kit import UrlTemplate
from ..blocks import Blocks
from .base import RustCallCollector
from .request_impl import RequestImpl


class TraitPathCalls(RustCallCollector):
    """One call per string a request type's `fn path` (or url/endpoint) can return."""

    CAPTURE = 'impl'

    def calls(self, file, impl) -> list:
        request = RequestImpl.of(impl)
        if request is None:
            return []
        test = self.workspace.is_test(file, impl)
        names = request.hints() | {file.path}
        out = []
        for name, fn in request.path_fns():
            for r in Blocks.returns(fn):
                for value, node, base in self._values.values(file, r):
                    url = UrlTemplate.split(value)
                    if url.path is None:
                        continue
                    hints = {h for h in names | {*base, *url.hints} if h}
                    function = f'{request.type_name}::{name}'
                    out.append(
                        self.call(file, file.line(node), url.path, request.method_of(node), function, hints, test)
                    )
        return out
