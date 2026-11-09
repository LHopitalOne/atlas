"""Where blueprints and routers are registered, and under which prefix."""

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import PythonValueResolver


class Registrations:
    """`app.register_blueprint(bp, url_prefix=...)` and `app.include_router(router, prefix=...)`: the prefix each
    blueprint or router (by the file and position of its constructor call) is registered under. A router included in
    another router (`parent.include_router(child)`, FastAPI's nested routers; Flask's nested blueprints) is also
    under the parent's whole prefix: the parent's own `prefix=` and whatever the parent is registered under. Read
    once per workspace and shared by the collectors that need it."""

    NAMES = frozenset({'register_blueprint', 'include_router'})
    PREFIXES = ('url_prefix', 'prefix')
    MAX_NESTING = 8  # routers included in routers, followed up to the app
    APPS = frozenset({'FastAPI', 'Flask', 'Quart'})  # an application: what it includes is under no router's prefix

    def __init__(self, workspace):
        self._workspace = workspace
        self._values = PythonValueResolver(workspace)
        self._prefixes = {}  # constructor key -> the prefix given where it is registered
        self._parents = {}  # constructor key -> (the including router's key, its own prefix)
        for source, call, _ in workspace.calls(self.NAMES):
            self._register(source, call)

    def _register(self, source, call):
        pos, kw = PythonSyntax.call_args(call)
        target = pos[0] if pos else kw.get('blueprint') or kw.get('router')
        found = self._workspace.names.value(source, target) if target is not None else None
        if found is None:
            return
        key = (found.source.path, found.node.start_byte)
        prefix = next((kw[k] for k in self.PREFIXES if k in kw), None)
        given = self._literal(prefix, Scope.at(source, call)) if prefix is not None else None
        parent = self._router(source, PythonSyntax.receiver(call))
        if parent is not None:
            self._parents[key] = (parent, given or '')
        elif given is not None:
            self._prefixes[key] = given

    def _router(self, source, receiver):
        """(key, own prefix) of the router or blueprint a registration is made on; None for an app or the unknown."""
        found = self._workspace.names.value(source, receiver) if receiver is not None else None
        if found is None or found.node.type != 'call' or PythonSyntax.callee(found.node) in self.APPS:
            return None
        _, kw = PythonSyntax.call_args(found.node)
        node = next((kw[k] for k in self.PREFIXES if k in kw), None)
        own = self._literal(node, Scope.module(found.source)) if node is not None else ''
        return (found.source.path, found.node.start_byte), own or ''

    def _literal(self, node, scope):
        v = self._values.resolve(node, scope)[0]
        return v.text if v.is_literal else None

    def prefix_for(self, source, constructor):
        """The prefix a blueprint or router was registered under, or None."""
        return self._prefix((source.path, constructor.start_byte), self.MAX_NESTING)

    def _prefix(self, key, depth):
        if key in self._parents and depth > 0:
            (parent, own), given = self._parents[key]
            return (self._prefix(parent, depth - 1) or '') + own + given
        return self._prefixes.get(key)
