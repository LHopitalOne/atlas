"""The words around a request that may name the service it goes to."""

from ..names import ItemPath
from ..syntax import RustSyntax


class RequestContext:
    """Hints from where a request is built: the impl and fn around it, what its client is bound to, and what is
    done with the request afterwards (`.send_to(state.upstream_relay())`)."""

    def __init__(self, workspace):
        self._workspace = workspace

    def hints(self, file, call, recv) -> set:
        hints = self._enclosing(call)
        hints |= self._client_definition(file, recv)
        n = call
        while file.has_outer_call(n):
            n = file.outer_call(n)
            hints.add(RustSyntax.text(n.child_by_field_name('function').child_by_field_name('field')))
            for a in RustSyntax.args(n):
                hints |= {RustSyntax.text(i) for i in RustSyntax.identifiers(a)}
        return hints

    @staticmethod
    def function_name(node):
        """'Type::fn' for a method, 'fn' for a free function, '' outside functions."""
        fn = RustSyntax.ancestor(node, ('function_item',))
        if fn is None:
            return ''
        name = RustSyntax.name(fn)
        impl = RustSyntax.ancestor(fn, ('impl_item',))
        if impl is not None:
            return ItemPath.last(impl.child_by_field_name('type')) + '::' + name
        return name

    @staticmethod
    def _enclosing(call):
        hints = set()
        impl = RustSyntax.ancestor(call, ('impl_item',))
        if impl is not None:
            for field in ('type', 'trait'):
                n = impl.child_by_field_name(field)
                if n is not None:
                    hints.add(ItemPath.strip_generics(RustSyntax.text(n)))
        fn = RustSyntax.ancestor(call, ('function_item',))
        if fn is not None:
            hints.add(RustSyntax.name(fn))
        return hints

    def _client_definition(self, file, recv):
        """The let or const the client comes from: `let client = reqwest::Client::builder()...`."""
        root = RustSyntax.chain_root(recv)
        if root is None or root.type != 'identifier':
            return set()
        value = self._workspace.binding(file, root)
        if value is not None:
            return {RustSyntax.text(value)}
        hit = self._workspace.const_value(file, root)
        return {RustSyntax.text(hit[1])} if hit is not None else set()
