"""Where routers are built: the outermost calls of method chains with a router step."""

import re

from ...syntax import RustSyntax


class RouterTops:
    """Finds the router expressions to evaluate in a file, skipping test code and local mock servers."""

    STEPS = frozenset({'route', 'nest', 'merge', 'route_service', 'nest_service', 'service', 'configure'})
    MARKERS = (b'Router', b'actix')  # a file without these builds no router
    # A server bound to an ephemeral loopback port is an in-process mock or helper, not a service's API.
    # Matched against the function's text with all whitespace removed.
    LOOPBACK = re.compile(r'\[127,0,0,1\],0\)|"(?:127\.0\.0\.1|localhost|\[::1\]):0"|Ipv[46]Addr::LOCALHOST\)?,0\)')

    def __init__(self, workspace):
        self._workspace = workspace
        self._loopback = {}  # function key -> whether it serves on an ephemeral loopback port

    def of(self, file):
        """The router tops of a file, in source order."""
        if file.tested or not file.mentions(*self.MARKERS):
            return []
        return [c for c in file.nodes('call') if not file.has_outer_call(c) and self._is_top(file, c)]

    def _is_top(self, file, call):
        n = call
        while n is not None and n.type == 'call_expression':
            fn = RustSyntax.method(n)
            if fn is None:
                return False
            if RustSyntax.text(fn.child_by_field_name('field')) in self.STEPS:
                return not self._workspace.in_test(call) and not self._serves_loopback(file, call)
            n = RustSyntax.unwrap(fn.child_by_field_name('value'))
        return False

    def _serves_loopback(self, file, node):
        """Whether the function around `node` binds an ephemeral loopback port: a local mock server."""
        fn = RustSyntax.ancestor(node, ('function_item',))
        if fn is None:
            return False
        k = file.key(fn)
        if k not in self._loopback:
            self._loopback[k] = bool(self.LOOPBACK.search(''.join(RustSyntax.text(fn).split())))
        return self._loopback[k]
