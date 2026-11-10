"""Helper functions that return a URL: `self._make_url(path)` is what the helper returns, with `path` filled in."""

from ..scope import Scope
from ..syntax import PythonSyntax
from .value import Marker, Value


class HelperHandlers:
    """Mixed into the Python resolver. A call to a function or method of this repository whose body returns one
    expression resolves to that expression, read in the helper with its parameters as markers, then filled with the
    call's arguments (read where the call is). A parameter with no argument stays a {placeholder}."""

    MAX_RETURNS = 1  # helpers with one return statement: several returns mean several URLs, left to the caller

    def helper_value(self, node, scope, depth):
        """The values a call to a URL-returning helper stands for, or None when it does not call one."""
        found = self._helper(node.child_by_field_name('function'), scope)
        if found is None:
            return None
        source, func = found
        body = PythonSyntax.body_nodes(func.child_by_field_name('body'))
        returned = [r for r in body if r.type == 'return_statement']
        if len(returned) != self.MAX_RETURNS or not returned[0].named_children:
            return None
        expr = returned[0].named_children[0]
        args = self._arguments(node, func, scope, depth)
        hint = frozenset({Value.hint(PythonSyntax.text(node.child_by_field_name('function')))})
        out = []
        for v in self.resolve(expr, Scope.at(source, expr), depth + 1):
            text = Marker.PATTERN.sub(lambda m: args.get(m.group(1), '{' + m.group(1) + '}'), v.text)
            out.append(Value(text, v.hints | hint, Value.LITERAL if v.is_known else Value.UNKNOWN))
        return out

    def _helper(self, fn, scope):
        """(source, function node) of a plain function or module function called by name, or of `self.method`."""
        if fn.type == 'attribute' and PythonSyntax.is_self(fn.child_by_field_name('object')) and scope.cls is not None:
            name = PythonSyntax.text(fn.child_by_field_name('attribute'))
            body = scope.cls.child_by_field_name('body')
            for st in body.named_children if body is not None else ():
                st = st.child_by_field_name('definition') if st.type == 'decorated_definition' else st
                if st is not None and st.type == 'function_definition' and PythonSyntax.name(st) == name:
                    return scope.source, st
            return None
        found = self._workspace.names.expression(scope.source, fn) if fn.type in ('identifier', 'attribute') else None
        return (found.source, found.node) if found and found.is_function else None

    def _arguments(self, call, func, scope, depth):
        """{parameter: the first value of its argument} for the arguments the call passes."""
        params = [p for p, _ in PythonSyntax.params(func)]
        if PythonSyntax.is_method(func) and params:
            params = params[1:]
        pos, kw = PythonSyntax.call_args(call)
        given = dict(zip(params, pos, strict=False)) | {k: v for k, v in kw.items() if k in params}
        return {p: self.resolve(a, scope, depth + 1)[0].text for p, a in given.items()}
