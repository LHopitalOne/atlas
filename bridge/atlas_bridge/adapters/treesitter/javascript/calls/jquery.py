"""jQuery's request functions: `$.ajax(settings)`, `$.ajax(url, settings)`, `$.get(url)`, `$.post(url)`,
`$.getJSON(url)`, on the global `$` / `jQuery` or on a name the 'jquery' module is imported as."""

from dataclasses import dataclass

from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .base import RequestCollector


@dataclass(frozen=True)
class AjaxFunction:
    """A request function of the jQuery object: its name, and the method it sends unless its settings give one
    (`ajax` reads it from `method` / `type`, GET by default)."""

    name: str
    method: str = 'GET'


class JQueryRequests(RequestCollector):
    """A call of one of the functions of TABLE on jQuery. Given a URL string, it sends to that URL; given a settings
    object, to its `url`, with the method its `method` or `type` names. Settings held by a parameter of a helper
    (`function call(args) { return $.ajax(args) }`) are filled in by the helper's callers. A URL that is not a path
    or an absolute URL is relative to the page, so it is left out. (`$.getScript` loads a script, not an API.)"""

    TABLE = (
        AjaxFunction('ajax'),
        AjaxFunction('get'),
        AjaxFunction('post', 'POST'),
        AjaxFunction('getJSON'),
    )
    LIBRARY = 'jquery'
    GLOBALS = frozenset({'$', 'jQuery'})  # what jQuery is called when a page loads it with a script tag
    METHOD_KEYS = ('method', 'type')  # jQuery reads both; `type` is the older name
    MENTIONS = tuple(f'.{f.name}('.encode() for f in TABLE)  # bytes a file must contain to call one
    NAMES = frozenset(f.name for f in TABLE)
    _BY_NAME = {f.name: f for f in TABLE}

    def claims(self, module, site):
        return super().claims(module, site) and site.is_member and self.is_jquery(module, site.receiver)

    def requests(self, builder, site):
        if not site.args:
            return []
        default = self._BY_NAME[site.name].method
        first, second = site.args[0], site.args[1] if len(site.args) > 1 else None
        if second is None and self._settings(builder, first):
            return builder.from_settings(site.node, first, default, self.METHOD_KEYS, require_path=True)
        if second is None and self._parameter(builder, first):  # a URL or a settings object: its callers tell
            builder.from_settings(site.node, first, default, self.METHOD_KEYS, require_path=True)
        method = builder.method(second, default, self.METHOD_KEYS) if site.name == 'ajax' else default
        keys = self.METHOD_KEYS
        return builder.build(site.node, None, first, method, require_path=True, options=second, method_keys=keys)

    @classmethod
    def is_jquery(cls, module, receiver):
        """`$`, `jQuery` or `window.$` not bound to anything else in the file, or a name 'jquery' is imported as."""
        receiver = JsSyntax.unwrap(receiver)
        if receiver is None:
            return False
        if receiver.type == 'member_expression':
            head = JsSyntax.text(receiver.child_by_field_name('object'))
            return head in CallSite.GLOBALS and JsSyntax.text(receiver.child_by_field_name('property')) in cls.GLOBALS
        if receiver.type != 'identifier':
            return False
        name = JsSyntax.text(receiver)
        imported = module.imports.get(name)
        source = imported[0] if imported is not None else module.imports.namespace(name)
        if source is not None:
            return source == cls.LIBRARY
        return name in cls.GLOBALS and module.scopes.binding(receiver, name) is None

    @staticmethod
    def _settings(builder, node):
        """The only argument is a settings object (`$.get({ url })`, `$.ajax(settings)`), not a URL: an object
        literal or a const bound to one."""
        node = JsSyntax.unwrap(node)
        if node.type == 'object':
            return True
        if node.type != 'identifier':
            return False
        bound = JsSyntax.unwrap(builder.module.scopes.lookup(node, JsSyntax.text(node)))
        return bound is not None and bound.type == 'object'

    @staticmethod
    def _parameter(builder, node):
        """The only argument is a parameter of the enclosing function: a URL string or a settings object, which
        only its callers tell, so the request is opened both ways (an argument fills in only the reading it fits)."""
        node = JsSyntax.unwrap(node)
        return node.type == 'identifier' and builder.params.is_parameter(node)
