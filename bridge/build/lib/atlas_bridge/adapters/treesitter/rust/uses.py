"""Use declarations: which full path each local name stands for."""

from .names import ItemPath
from .syntax import RustSyntax


class UseTree:
    """The names one `use` argument brings in: `axum::routing::{get, head as axum_head}` ->
    {'get': 'axum::routing::get', 'axum_head': 'axum::routing::head'}."""

    @staticmethod
    def read(node) -> dict[str, str]:
        """{local name: full path} of the names one `use` argument brings in. Iterative: use trees can nest deeply."""
        out = {}
        stack = [(node, '')]
        while stack:
            node, prefix = stack.pop()
            t = node.type
            if t == 'use_as_clause':
                path = prefix + ItemPath.strip_generics(RustSyntax.text(node.child_by_field_name('path')))
                out[RustSyntax.text(node.child_by_field_name('alias'))] = path
            elif t == 'scoped_use_list':
                stack += UseTree._scoped(node, prefix)
            elif t == 'use_list':
                stack += [(c, prefix) for c in node.named_children]
            elif t in RustSyntax.NAMES:
                full = prefix + RustSyntax.text(node)
                out[full.split('::')[-1]] = full
        return out

    @staticmethod
    def _scoped(node, prefix):
        p = node.child_by_field_name('path')
        lst = node.child_by_field_name('list')
        if lst is None:
            return []
        return [(lst, prefix + (RustSyntax.text(p) + '::' if p is not None else ''))]
