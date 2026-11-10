"""Where blueprints and routers are registered, and under which prefix."""

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import PythonValueResolver


class Registrations:
    """`app.register_blueprint(bp, url_prefix=...)` and `app.include_router(router, prefix=...)`: the prefix each
    blueprint or router (by the file and position of its constructor call) is registered under. Read once per
    workspace and shared by the collectors that need it."""

    NAMES = frozenset({'register_blueprint', 'include_router'})

    def __init__(self, workspace):
        self._workspace = workspace
        self._values = PythonValueResolver(workspace)
        self._prefixes = {}  # (path, constructor start byte) -> registered prefix
        for source, call, _ in workspace.calls(self.NAMES):
            self._register(source, call)

    def _register(self, source, call):
        pos, kw = PythonSyntax.call_args(call)
        target = pos[0] if pos else kw.get('blueprint') or kw.get('router')
        prefix = kw.get('url_prefix') if 'url_prefix' in kw else kw.get('prefix')
        if target is None or prefix is None:
            return
        found = self._workspace.names.value(source, target)
        v = self._values.resolve(prefix, Scope.at(source, call))[0]
        if found is not None and v.is_literal:
            self._prefixes[(found.source.path, found.node.start_byte)] = v.text

    def prefix_for(self, source, constructor):
        """The prefix a blueprint or router was registered under, or None."""
        return self._prefixes.get((source.path, constructor.start_byte))
