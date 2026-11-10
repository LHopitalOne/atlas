"""actix-web attribute routes: `#[get("/p")]`, `#[route("/p", method = "GET")]` on a handler fn."""

from .....core.http import ANY
from ...kit import StringTemplate
from ..syntax import RustSyntax
from .found import AttributeRoute
from .paths import RoutePath


class ActixAttributes:
    """Every attribute route in the workspace, by the key of the fn it is on."""

    VERBS = frozenset({'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace', 'connect'})
    ROUTE = 'route'

    def __init__(self, files):
        self._routes = {}  # fn key -> [AttributeRoute]
        for f in files:
            for a in f.nodes('attr'):
                self._read(f, a)

    def of(self, file, fn) -> list:
        return self._routes.get(file.key(fn), [])

    def items(self):
        """(fn key, [AttributeRoute]) in source order."""
        return self._routes.items()

    def _read(self, f, attr_item):
        attr = next((c for c in attr_item.named_children if c.type == 'attribute'), None)
        if attr is None or not attr.named_children:
            return
        name = RustSyntax.text(attr.named_children[0]).split('::')[-1]
        args = attr.child_by_field_name('arguments')
        if (name not in self.VERBS and name != self.ROUTE) or args is None:
            return
        lits = [StringTemplate.of(c) for c in args.named_children if c.type in RustSyntax.STRINGS]
        if not lits or not lits[0].startswith('/'):
            return
        fn = self._item_after(attr_item)
        if fn is not None and fn.type == 'function_item':
            route = AttributeRoute(RoutePath.canonical(lits[0]), self._methods(name, lits), f.line(attr_item), f, fn)
            self._routes.setdefault(f.key(fn), []).append(route)

    @classmethod
    def _methods(cls, name, lits):
        if name == cls.ROUTE:  # #[route("/p", method = "GET", method = "HEAD")]
            return {m.upper() for m in lits[1:] if m.isalpha()} or {ANY}
        return {name.upper()}

    @staticmethod
    def _item_after(attr_item):
        fn = attr_item.next_named_sibling
        while fn is not None and fn.type in ('attribute_item', 'line_comment', 'block_comment'):
            fn = fn.next_named_sibling
        return fn
