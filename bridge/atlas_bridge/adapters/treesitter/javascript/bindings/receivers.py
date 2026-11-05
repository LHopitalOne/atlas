"""Receivers: what the object a route or request method is called on looks like (router, HTTP client, map)."""

import re

from .....core.words import Words
from ..syntax.members import Members
from ..syntax.nodes import JsSyntax
from .imports import ImportTable
from .scopes import Scopes


class Receivers:
    """Reads receivers by name and, through the file's bindings, by how they were made."""

    # the last name of an HTTP client: `api`, `this.apiClient`, `request(app)`, `axios`, `ky`
    CLIENT = re.compile(r'(api|client|https?|axios|request|superagent|agent|fetcher|^ky|^got)$', re.I)
    # words of receivers whose get/put/delete take keys, not URLs
    NOT_CLIENT = frozenset(
        {
            'headers',
            'params',
            'query',
            'map',
            'cache',
            'caches',
            'storage',
            'cookies',
            'env',
            'form',
            'set',
            'store',
            'registry',
            'options',
            'config',
            'settings',
        }
    )
    # initializers of objects whose get/put/delete take keys: `new Map()`, `caches.open('v1')`
    NOT_CLIENT_INIT = re.compile(r'^(new\s+(Map|Set|WeakMap|URLSearchParams|Headers|FormData)\b|caches\.open\b)')
    KEY_VALUE = re.compile(r'redis|memcache|valkey|keyv|cache|storage|localforage', re.I)  # get/del take keys
    ROUTER = re.compile(r'(app|router|routes|server|fastify|hono)$', re.I)  # the last name of a router
    ROUTER_INIT = re.compile(r'\b(Router|express|Hono|fastify|Koa|createServer)\s*\(', re.I)  # how a router is made
    CHAINS = {'member_expression': 'object', 'call_expression': 'function'}  # chain node -> the field it extends

    def __init__(self, scopes: Scopes, imports: ImportTable):
        self._scopes = scopes
        self._imports = imports

    @classmethod
    def is_client(cls, obj):
        """The receiver's last name ends like an HTTP client's."""
        return bool(cls.CLIENT.search(JsSyntax.last_name(obj)))

    @classmethod
    def words(cls, name):
        """'QUERY_API_CLIENT' / 'routeMap' -> lower-case words."""
        return Words.ordered(name)

    @classmethod
    def is_key_value(cls, hints):
        """Some hint about the receiver names a cache or key-value store."""
        return any(cls.KEY_VALUE.search(h) for h in hints)

    def is_router(self, obj):
        """Named like a router, or bound to `express()`, `Router()`, `new Hono()`..."""
        if self.ROUTER.search(JsSyntax.last_name(obj)):
            return True
        if obj.type == 'identifier':
            value = self._scopes.lookup(obj, JsSyntax.text(obj))
            return value is not None and bool(self.ROUTER_INIT.search(JsSyntax.text(value)))
        return False

    def is_not_client(self, obj):
        """A Map, a cache, URLSearchParams: their keys only look like paths."""
        if set(self.words(JsSyntax.last_name(obj))) & self.NOT_CLIENT:
            return True
        if obj.type == 'identifier':
            value = self._scopes.lookup(obj, JsSyntax.text(obj))
            return value is not None and bool(self.NOT_CLIENT_INIT.match(JsSyntax.text(JsSyntax.unwrap(value))))
        return False

    def hints(self, obj):
        """Where the client comes from: its binding's initializer, the import it comes from, a class field."""
        out = set()
        head = obj
        while head.type in self.CHAINS:
            head = JsSyntax.unwrap(head.child_by_field_name(self.CHAINS[head.type]))
        if head.type == 'identifier':
            value = self._scopes.lookup(head, JsSyntax.text(head))
            if value is not None:
                out.add(JsSyntax.text(value))
            imported = self._imports.get(JsSyntax.text(head))
            if imported:
                out.add(imported[0])
        elif head.type == 'this' and obj.type == 'member_expression':
            field = JsSyntax.text(obj.child_by_field_name('property'))
            out.update(JsSyntax.text(v) for v in Members.of_this(obj, field))
        return out
