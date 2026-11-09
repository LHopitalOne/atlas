"""What a Django view expression serves: its handler name and HTTP methods."""

from ......core.http import ANY
from ...syntax import PythonSyntax
from ...verbs import HttpVerbs


class ViewMethods:
    """`View.as_view()` serves the verbs its class (or, when it defines none, its direct bases) defines methods for;
    a decorated view (`csrf_exempt(View.as_view())`) is read through; any other view serves ANY. A route helper
    call that passes views as keywords named like HTTP methods (`GET=view`) serves those methods."""

    BASES = ('identifier', 'attribute')
    SEQUENCES = frozenset({'tuple', 'parenthesized_expression'})  # `GET=(view, options)`: the view comes first

    def __init__(self, workspace):
        self._workspace = workspace

    def handler_and_methods(self, source, view):
        """(handler text, frozenset of methods)."""
        if view.type == 'call':
            fn = view.child_by_field_name('function')
            if fn.type == 'attribute' and PythonSyntax.text(fn.child_by_field_name('attribute')) == 'as_view':
                cls_expr = fn.child_by_field_name('object')
                return PythonSyntax.text(cls_expr), self._class_methods(source, cls_expr)
            pos, _ = PythonSyntax.call_args(view)
            if pos and pos[0].type == 'call':  # a decorated view: csrf_exempt(View.as_view())
                return self.handler_and_methods(source, pos[0])
        return PythonSyntax.text(view), frozenset({ANY})

    @classmethod
    def keyword_views(cls, call):
        """[(METHOD, handler text)] of the keyword arguments of a call named like HTTP methods (GET=, POST=...)."""
        _, kw = PythonSyntax.call_args(call)
        out = []
        for key, view in kw.items():
            if key in HttpVerbs.METHODS and view is not None:
                while view.type in cls.SEQUENCES and view.named_children:
                    view = view.named_children[0]
                out.append((key, PythonSyntax.text(view)))
        return out

    def _find_class(self, source, expr):
        """(file, class node) of a class expression: by import, else by name (production code first)."""
        found = self._workspace.names.expression(source, expr)
        if found and found.is_class:
            return found.source, found.node
        name = PythonSyntax.text(expr).split('.')[-1]
        candidates = self._workspace.classes(name)
        production = [c for c in candidates if not c[0].test] or candidates
        return production[0] if production else (None, None)

    def _class_methods(self, source, expr):
        class_file, cls = self._find_class(source, expr)
        if cls is None:
            return frozenset({ANY})
        methods = self._own_methods(cls)
        if not methods:
            bases = cls.child_by_field_name('superclasses')
            for b in bases.named_children if bases is not None else ():
                if b.type in self.BASES:
                    _, base = self._find_class(class_file, b)
                    if base is not None:
                        methods |= self._own_methods(base)
        return frozenset(methods) or frozenset({ANY})

    @staticmethod
    def _own_methods(cls):
        out = set()
        body = cls.child_by_field_name('body')
        for st in body.named_children if body is not None else ():
            if st.type == 'decorated_definition':
                st = st.child_by_field_name('definition')
            if st is not None and st.type == 'function_definition' and PythonSyntax.name(st) in HttpVerbs.NAMES:
                out.add(PythonSyntax.name(st).upper())
        return out
