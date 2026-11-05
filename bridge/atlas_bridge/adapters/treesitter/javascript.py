"""javascript / typescript: HTTP routes (Express, Koa-router, Fastify, Hono) and requests (fetch, axios, HTTP clients).

Routes: `<app|router|server>.get('/orders/:id', ...handlers)`, `router.route('/p').get(h).post(h)`,
`fastify.route({method, url, handler})`. `app.use('/prefix', routerVar)` prefixes the routes of `routerVar` when it is
defined in the same file or imported from another file of the repository.

Requests: `fetch(url, {method})`, `axios(config)`, `axios.get(url)`, `<client>.get/post/...(url)`,
`<client>.request(config)`. URLs are resolved from string and template literals, `+` concatenation and const/let
bindings in the enclosing function or module. A client's base path is prepended to the request path: the
`baseURL`/`baseUrl`/`prefixUrl` given where it is made (`axios.create({baseURL})`, `new Client({baseUrl})`), or the
default of a client class of the repository (`this.baseUrl = options.baseUrl ?? '/api/0'`), reached through
`new Client()`, a parameter typed `Client`, a function that returns `new Client()`, or a module-level client.
"""

import dataclasses
import os
import re

import tree_sitter as ts

from ...core.http import ANY, Call, Extraction, PathTemplate, Route
from . import common

FRAMEWORK = 'express'
VERBS = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
ROUTE_VERBS = (*VERBS, 'all', 'del')
REQUEST_METHODS = ('request', 'requestPromise')
DIRECT = ('fetch', 'axios', 'got', 'ky')  # functions that send a request when called
GLOBALS = ('window', 'globalThis', 'self', 'global')
NAMES = (*ROUTE_VERBS, *REQUEST_METHODS, *DIRECT, 'route', 'use')
PRECHECK = (
    b'fetch',
    b'axios',
    b'got(',
    b'ky(',
    b'.get(',
    b'.post(',
    b'.put(',
    b'.delete(',
    b'.del(',
    b'.patch(',
    b'.head(',
    b'.options(',
    b'.all(',
    b'.route(',
    b'.request(',
    b'.requestPromise(',
    b'.use(',
)
BASE_KEYS = ('baseUrl', 'baseURL', 'prefixUrl', 'prefixURL', 'basePath')  # where a client keeps its base
BASE_BYTES = tuple(k.encode() for k in BASE_KEYS)
CONSTRUCTED = re.compile(rb'\bnew\s+([A-Za-z_$][\w$]*)\s*\(')
QUERY = '(call_expression function: [(identifier) @name (member_expression property: (property_identifier) @name)] '
QUERY += '(#any-of? @name ' + ' '.join(f'"{n}"' for n in NAMES) + ')) @call'

CLIENT = re.compile(r'(api|client|https?|axios|request|superagent|agent|fetcher|^ky|^got)$', re.I)
NOT_CLIENT = {
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
NOT_CLIENT_INIT = re.compile(r'^(new\s+(Map|Set|WeakMap|URLSearchParams|Headers|FormData)\b|caches\.open\b)')
KEY_VALUE = re.compile(r'redis|memcache|valkey|keyv|cache|storage|localforage', re.I)  # get/del take keys, not URLs
BASE_NAME = re.compile(r'url|uri|base|host|server|endpoint|addr|prefix|upstream|origin|root', re.I)
PATH_NAME = re.compile(r'url|uri|path|endpoint|route|href', re.I)  # an expression that holds a path or URL
ROUTER = re.compile(r'(app|router|routes|server|fastify|hono)$', re.I)
ROUTER_INIT = re.compile(r'\b(Router|express|Hono|fastify|Koa|createServer)\s*\(', re.I)  # how a router is made
TEST_FUNCS = {'describe', 'it', 'test', 'beforeEach', 'beforeAll', 'afterEach', 'afterAll', 'suite'}
WRAPPERS = {
    'parenthesized_expression',
    'as_expression',
    'satisfies_expression',
    'non_null_expression',
    'await_expression',
}
FUNCTIONS = {
    'function_declaration',
    'generator_function_declaration',
    'function_expression',
    'function',
    'generator_function',
    'arrow_function',
    'method_definition',
}
CLASSES = {'class_declaration', 'class', 'abstract_class_declaration'}
SCOPES = {'statement_block', 'program'}
BINDERS = FUNCTIONS | {'for_in_statement', 'catch_clause'}  # nodes that bind names without a declaration
MODULE_EXTS = ('', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.cjs')
MAX_DEPTH = 5
MAX_HINT = 200
MAX_URL = 1000  # a resolved URL longer than this is not a URL
UNKNOWN_BASE = '/{base}'  # a repository client whose base path cannot be read


def extract(repo, root, paths):
    out = Extraction()
    files, pending, constructed = [], [], {}
    clients = _Clients()
    for path in paths:
        source = common.read(root, path)
        if source is None:
            continue
        constructed[path] = set(CONSTRUCTED.findall(source))
        has_base = any(k in source for k in BASE_BYTES)
        if not has_base and not any(k in source for k in PRECHECK):
            continue
        f = _File(repo, path, source)
        f.scan()
        if has_base:
            clients.add('class', f.client_classes(), f.test_file)
        pending += f.calls
        if f.routes or f.mounts:
            files.append(f)
    names = {n.encode() for n in clients.classes}
    for path, made in constructed.items():
        if names & made:
            f = _File(repo, path, common.read(root, path))
            factories, variables = f.client_factories(clients.classes)
            clients.add('factory', factories, f.test_file)
            clients.add('var', variables, f.test_file)
    out.calls += [_finish(call, path, client, clients) for call, path, client in pending]
    out.routes += _mounted_routes(repo, files)
    return out


def _finish(call, path, client, clients):
    """The call with its client's base path in front of its path."""
    base = clients.base(client) if client is not None else None
    if base and base != '/' and path != base and not path.startswith(base.rstrip('/') + '/'):
        path = base.rstrip('/') + '/' + path.lstrip('/')
    return dataclasses.replace(call, path=PathTemplate.parse(path))


class _Clients:
    """What the repository says about its HTTP clients, by name: classes, functions that make one, module variables.

    A spec is ('base', path), ('class', name), ('factory', name) or ('var', name); `base` follows them to a path.
    """

    def __init__(self):
        self.classes, self.factories, self.vars = {}, {}, {}
        self._test = {}

    def add(self, kind, found, test):
        table = {'class': self.classes, 'factory': self.factories, 'var': self.vars}[kind]
        for name, value in found.items():
            key = (kind, name)
            if name not in table or (self._test[key] and not test):  # code outside tests wins
                table[name], self._test[key] = {value}, test
            elif self._test[key] == test:
                table[name].add(value)

    def base(self, spec, depth=0):
        kind, name = spec
        if kind == 'base':
            return name
        if depth >= MAX_DEPTH:
            return None
        if kind == 'class':
            found = self.classes.get(name)
            if found is None:
                return None  # not a client class of this repository
            return next(iter(found)) if len(found) == 1 else UNKNOWN_BASE
        table = self.factories if kind == 'factory' else self.vars
        found = table.get(name)
        if found is None or len(found) != 1:
            return None
        return self.base(next(iter(found)), depth + 1)


# ---- per file -----------------------------------------------------------------------------------------------------


class _File:
    def __init__(self, repo, path, source):
        self.repo, self.path = repo, path
        grammar = common.EXTENSIONS.get(os.path.splitext(path)[1], 'javascript')
        self.lang = common.language(grammar)
        self.root = common.parse(grammar, source).root_node
        self.test_file = common.is_test_path(path)
        self.routes = []  # (receiver name, path, methods, handler, line)
        self.mounts = []  # (parent receiver name, prefix, child expression node)
        self.calls = []  # (call without its path, path, client spec or None)
        self._scopes = {}
        self._params = {}
        self._resolved = {}
        self._imports = None
        self._types = None

    def scan(self):
        cursor = ts.QueryCursor(_query(self.lang))
        for _, caps in cursor.matches(self.root):
            node, name = caps['call'][0], common.text(caps['name'][0])
            try:
                self._visit(node, name)
            except RecursionError:  # pragma: no cover - pathological nesting
                continue

    def _visit(self, node, name):
        fn = node.child_by_field_name('function')
        args = _args(node)
        if fn.type == 'identifier':
            if name in DIRECT:
                self._direct(node, name, args)
            return
        obj = _unwrap(fn.child_by_field_name('object'))
        if name in DIRECT:
            if common.text(obj) in GLOBALS:
                self._direct(node, name, args)
            elif name == 'fetch' and _is_client(obj):
                self._request(node, obj, args, 'GET')
        elif name == 'use':
            self._mount(obj, args)
        elif name == 'route':
            if args and _unwrap(args[0]).type == 'object':
                self._fastify(obj, node, args[0])
        elif name in REQUEST_METHODS:
            self._request(node, obj, args, 'GET', require_path=not _is_client(obj))
        elif not self._route(node, obj, name, args):
            self._verb_call(node, obj, name, args)

    # -- routes --

    def _route(self, node, obj, verb, args):
        """`router.route('/p').get(h)` or `app.get('/p', h)`: records the route and returns True."""
        method = _method_set(verb)
        n = obj
        while n.type == 'call_expression':
            f = n.child_by_field_name('function')
            if f.type != 'member_expression':
                break
            prop = common.text(f.child_by_field_name('property'))
            inner = _args(n)
            if prop == 'route' and inner and _unwrap(inner[0]).type == 'string':
                receiver = _unwrap(f.child_by_field_name('object'))
                self._add_route(receiver, common.string_value(_unwrap(inner[0])), method, args, node)
                return True
            if prop not in ROUTE_VERBS:
                break
            n = _unwrap(f.child_by_field_name('object'))
        strings = [i for i, a in enumerate(args[:2]) if _unwrap(a).type == 'string']
        if not strings or len(args) < 2 or not self._is_router(obj):
            return False
        i = strings[-1] if len(strings) == 2 else strings[0]  # koa-router: router.get('name', '/path', h)
        if i == len(args) - 1:
            return False
        self._add_route(obj, common.string_value(_unwrap(args[i])), method, args[i + 1 :], node)
        return True

    def _is_router(self, obj):
        if ROUTER.search(_last_name(obj)):
            return True
        if obj.type == 'identifier':
            value = self._lookup(obj, common.text(obj))
            return value is not None and bool(ROUTER_INIT.search(common.text(value)))
        return False

    def _add_route(self, receiver, path, methods, handlers, node):
        handler = ''
        if handlers:
            last = _unwrap(handlers[-1])
            if last.type in ('identifier', 'member_expression'):
                handler = common.text(last)
        self.routes.append((common.text(receiver), path, methods, handler, common.line(node)))

    def _fastify(self, obj, node, config):
        url = _prop(config, 'url') or _prop(config, 'path')
        if url is None or _unwrap(url).type != 'string':
            return
        method = _prop(config, 'method')
        methods = frozenset({ANY})
        if method is not None:
            method = _unwrap(method)
            values = [method] if method.type == 'string' else [x for x in method.named_children if x.type == 'string']
            if values:
                methods = frozenset().union(*(_method_set(common.string_value(v)) for v in values))
        handler = _prop(config, 'handler')
        self._add_route(obj, common.string_value(_unwrap(url)), methods, [handler] if handler else [], node)

    def _mount(self, obj, args):
        if len(args) >= 2 and _unwrap(args[0]).type == 'string':
            self.mounts.append((common.text(obj), common.string_value(_unwrap(args[0])), _unwrap(args[-1])))

    # -- requests --

    def _direct(self, node, name, args):
        if not args:
            return
        first = _unwrap(args[0])
        if name == 'axios' and first.type == 'object':
            self._config_call(node, None, first)
            return
        options = args[1] if len(args) > 1 else None
        self._emit(node, None, args[0], _option_method(self, options, 'GET'))

    def _request(self, node, obj, args, default, require_path=False):
        if not args:
            return
        first = _unwrap(args[0])
        if first.type == 'object':
            if not require_path:
                self._config_call(node, obj, first)
            return
        if require_path and self._not_client(obj):
            return
        options = args[1] if len(args) > 1 else None
        self._emit(node, obj, args[0], _option_method(self, options, default), require_path)

    def _config_call(self, node, obj, config):
        url = _prop(config, 'url')
        if url is not None:
            self._emit(node, obj, url, _option_method(self, config, 'GET'))

    def _verb_call(self, node, obj, verb, args):
        if not args or verb == 'all':
            return
        method = 'DELETE' if verb in ('del', 'delete') else verb.upper()
        is_client = _is_client(obj)
        if not is_client and self._not_client(obj):
            return  # a Map, a cache, URLSearchParams: their keys only look like paths
        self._emit(node, obj, args[0], method, require_path=not is_client)

    def _not_client(self, obj):
        if set(_words(_last_name(obj))) & NOT_CLIENT:
            return True
        if obj.type == 'identifier':
            value = self._lookup(obj, common.text(obj))
            return value is not None and bool(NOT_CLIENT_INIT.match(common.text(_unwrap(value))))
        return False

    def _emit(self, node, obj, url_node, method, require_path=False):
        if _unwrap(url_node).type == 'number':
            return
        hints = set()
        value = self._value(url_node, 0, hints)
        if value is None or not re.search(r'[\w/]', re.sub(r'\{[^{}]*\}', '', value)):
            return  # entirely dynamic: nothing to match
        path_like = _path_like(value)
        if require_path and not path_like:
            return
        receiver = self._receiver_hints(obj) if obj is not None else set()
        if not path_like and (':' in value or any(KEY_VALUE.search(h) for h in receiver)):
            return  # a cache or key-value key ('user:42', 'session'), not a request path
        path, base = common.split_url(re.sub(r'(?<=/)[:$]([A-Za-z_]\w*)', r'{\1}', value))
        if path is None:
            return
        hints.update(base)
        hints.update(_names_in(url_node))
        client = None
        if obj is not None:
            hints.add(common.text(obj))
            hints.update(receiver)
            if not base and '://' not in value:  # a relative path: the client's base goes in front
                client = self._client(obj, hints)
        function, cls = _enclosing(node)
        hints.update(h for h in (function, cls, self.path) if h)
        call = Call(
            self.repo,
            self.path,
            common.line(node),
            None,
            method,
            function=function,
            hints=frozenset(h[:MAX_HINT] for h in hints if h),
            test=self.test_file or _in_test(node),
        )
        self.calls.append((call, path, client))

    def _receiver_hints(self, obj):
        """Where the client comes from: its binding's initializer, the import it comes from, a class field."""
        out = set()
        head = obj
        while head.type in ('member_expression', 'call_expression'):
            head = _unwrap(head.child_by_field_name('object' if head.type == 'member_expression' else 'function'))
        if head.type == 'identifier':
            value = self._lookup(head, common.text(head))
            if value is not None:
                out.add(common.text(value))
            source = self.imports().get(common.text(head))
            if source:
                out.add(source[0])
        elif head.type == 'this' and obj.type == 'member_expression':
            field = common.text(obj.child_by_field_name('property'))
            out.update(common.text(v) for v in _member_values(obj, field))
        return out

    # -- clients and their base paths --

    def _client(self, obj, hints):
        """A spec for the client `obj` is (see _Clients), or None when nothing says where it comes from."""
        obj = _unwrap(obj)
        if obj.type == 'identifier':
            name = common.text(obj)
            kind, node = self._binding(obj, name)
            if kind == 'value':
                return self._client_of(node, hints, 0)
            if kind == 'param':
                return _typed(_param_type(node, name) or self._member_types().get(name))
            imported = self.imports().get(name)
            if imported is not None:
                return ('var', name if imported[1] == 'default' else imported[1])
            return None
        if obj.type == 'member_expression':  # this.api, this.props.api, props.api
            field = common.text(obj.child_by_field_name('property'))
            if _unwrap(obj.child_by_field_name('object')).type == 'this':
                for value in _member_values(obj, field):
                    spec = self._client_of(value, hints, 0)
                    if spec is not None:
                        return spec
            return _typed(self._member_types().get(field))
        if obj.type in ('call_expression', 'new_expression'):
            return self._client_of(obj, hints, 0)
        return None

    def _member_types(self):
        """{name: type} for typed members of the file's interfaces, object types and classes (`api: Client`)."""
        if self._types is None:
            self._types = {}
            for n in common.walk(self.root, {'property_signature', 'public_field_definition'}):
                name = common.text(n.child_by_field_name('name'))
                self._types.setdefault(name, _first_type(n.child_by_field_name('type')))
        return self._types

    def _client_of(self, value, hints, depth):
        """The client spec of an expression that makes or names a client."""
        value = _unwrap(value)
        if value is None or depth >= MAX_DEPTH:
            return None
        if value.type in ('new_expression', 'call_expression'):
            args = _args(value)
            base = self._base_option(args[0], hints) if args else None
            if base is not None:
                return ('base', base)
            callee = value.child_by_field_name('constructor' if value.type == 'new_expression' else 'function')
            if callee is not None and callee.type == 'identifier':
                return ('class' if value.type == 'new_expression' else 'factory', common.text(callee))
            return None
        if value.type == 'identifier':
            name = common.text(value)
            kind, node = self._binding(value, name)
            if kind == 'value':
                return self._client_of(node, hints, depth + 1)
            if name in self.imports():
                imported = self.imports()[name]
                return ('var', name if imported[1] == 'default' else imported[1])
        return None

    def _base_option(self, options, hints):
        """The path of the base URL in a client's options object (`{baseURL: 'http://orders/api'}` -> '/api')."""
        for key in BASE_KEYS:
            node = _prop(options, key)
            if node is not None:
                value = self._value(node, 0, hints)
                path, hosts = common.split_url(value or '')
                hints.update(hosts)
                return path or ''
        return None

    def client_classes(self):
        """{class name: default base path} for classes that keep a base URL in a field."""
        out = {}
        for cls in common.walk(self.root, CLASSES):
            if not cls.is_named:  # the `class` keyword
                continue
            name = common.text(cls.child_by_field_name('name'))
            for key in BASE_KEYS:
                values = _field_values(cls, key)
                if name and values:
                    out[name] = self._default_base(values)
                    break
        return out

    def _default_base(self, values):
        for v in values:
            value = self._value(v, 0, set())
            if _unwrap(v).type == 'string' and not value:
                return ''  # baseUrl = ''
            path = common.split_url(value)[0] if _literal(value) else None
            if path is not None and not path.startswith('/{'):
                return path
        return UNKNOWN_BASE

    def client_factories(self, classes):
        """({function: spec}, {module variable: spec}) for functions and variables that make a client of `classes`."""
        factories, variables = {}, {}
        for new in common.walk(self.root, {'new_expression'}):
            if common.text(new.child_by_field_name('constructor')) not in classes:
                continue
            spec = self._client_of(new, set(), 0)
            fn = common.ancestor(new, FUNCTIONS)
            while fn is not None and not _function_name(fn):  # `useMemo(() => new Client())` inside a hook
                fn = common.ancestor(fn, FUNCTIONS)
            if fn is not None:
                if _returns(fn):
                    factories.setdefault(_function_name(fn), spec)
                continue
            parent = new.parent
            while parent is not None and parent.type in WRAPPERS:
                parent = parent.parent
            if parent is not None and parent.type == 'variable_declarator':
                variables.setdefault(common.text(parent.child_by_field_name('name')), spec)
        return factories, variables

    # -- values --

    def _value(self, node, depth, hints):
        """The value of a URL expression as a template; unknown parts become {name}."""
        node = _unwrap(node)
        t = node.type
        if t == 'string':
            return common.string_value(node)
        if t == 'template_string':
            out = ''
            for c in node.children:
                if c.type in ('string_fragment', 'escape_sequence'):
                    out += common.text(c)
                elif c.type == 'template_substitution':
                    inner = c.named_children
                    part = self._value(inner[0], depth, hints) if inner else '{param}'
                    out = _join(out, part, inner[0] if inner else None)
            return out
        if t == 'binary_expression':
            op = common.text(node.child_by_field_name('operator'))
            right_node = node.child_by_field_name('right')
            left = self._value(node.child_by_field_name('left'), depth, hints)
            right = self._value(right_node, depth, hints)
            if op == '+':
                return _join(left, right, right_node)
            if op in ('||', '??'):
                return left if _literal(left) or not _literal(right) else right
            return '{' + common.placeholder(common.text(node)) + '}'
        if t == 'ternary_expression':
            return self._value(node.child_by_field_name('consequence'), depth, hints)
        if t == 'identifier':
            return self._identifier(node, depth, hints)
        if t == 'number':
            return common.text(node)
        if t == 'call_expression':  # a URL builder: getUrl('/orders/$id/', {...})
            args = _args(node)
            first = _unwrap(args[0]) if args else None
            if first is not None and first.type in ('string', 'template_string'):
                value = self._value(first, depth, hints)
                if _path_like(value):
                    hints.add(common.text(node.child_by_field_name('function')))
                    return value
        if t == 'new_expression' and common.text(node.child_by_field_name('constructor')) == 'URL':
            args = _args(node)
            if args:
                for a in args[1:]:
                    hints.add(common.text(a))
                    if _unwrap(a).type == 'identifier':
                        self._value(a, depth, hints)
                return self._value(args[0], depth, hints)
        hints.add(common.text(node))
        return '{' + common.placeholder(common.text(node)) + '}'

    def _identifier(self, node, depth, hints):
        """The value bound to an identifier, or {name}. Each binding is resolved once per file."""
        name = common.text(node)
        hints.add(name)
        kind, value = self._binding(node, name) if depth < MAX_DEPTH else (None, None)
        if kind == 'value':
            cached = self._resolved.get(value.id)
            if cached is None:
                found = {common.text(value)}
                resolved = self._value(value, depth + 1, found)
                cached = self._resolved[value.id] = (resolved, found)
            resolved, found = cached
            hints.update(found)
            if _literal(resolved) and len(resolved) <= MAX_URL:
                return resolved
        return '{' + name + '}'

    def _lookup(self, node, name):
        """The initializer of the const/let/var `name` visible from `node`; None if a parameter shadows it."""
        kind, value = self._binding(node, name)
        return value if kind == 'value' else None

    def _binding(self, node, name):
        """('value', initializer) or ('param', parameter) for the nearest binding of `name` around `node`."""
        scope = node.parent
        while scope is not None:
            if scope.type in SCOPES:
                kind, found = self._bindings(scope).get(name, (None, None))
                if found is not None and found.id != node.id and not _contains(found, node):
                    return kind, found
            elif scope.type in BINDERS:
                param = self._parameters(scope).get(name)
                if param is not None:
                    return 'param', param
            scope = scope.parent
        return None, None

    def _bindings(self, scope):
        b = self._scopes.get(scope.id)
        if b is None:
            b = {}
            for child in scope.named_children:
                if child.type == 'export_statement':
                    child = child.child_by_field_name('declaration') or child
                if child.type in ('lexical_declaration', 'variable_declaration'):
                    for d in child.named_children:
                        name, value = d.child_by_field_name('name'), d.child_by_field_name('value')
                        if value is None or name is None:
                            continue
                        if name.type == 'identifier':
                            b.setdefault(common.text(name), ('value', value))
                        else:  # const {api} = props: bound, but to no value we can read
                            b.update((n, ('param', d)) for n in _pattern_names(name) if n not in b)
            self._scopes[scope.id] = b
        return b

    def _parameters(self, node):
        """{name: parameter node} for a function's parameters, a for-in/of variable or a catch parameter."""
        found = self._params.get(node.id)
        if found is None:
            found = {}
            if node.type == 'for_in_statement':
                params = [node.child_by_field_name('left')]
            elif node.type == 'catch_clause':
                params = [node.child_by_field_name('parameter')]
            else:
                single = node.child_by_field_name('parameter')
                formal = node.child_by_field_name('parameters')
                params = [single] if single is not None else (formal.named_children if formal is not None else [])
            for p in params:
                for name in _pattern_names(p):
                    found.setdefault(name, p)
            self._params[node.id] = found
        return found

    def imports(self):
        """name -> (module source, imported name or 'default') for import statements and `x = require('...')`."""
        if self._imports is None:
            self._imports = {}
            for child in self.root.named_children:
                if child.type == 'import_statement':
                    self._import_statement(child)
                elif child.type in ('lexical_declaration', 'variable_declaration'):
                    for d in child.named_children:
                        name, value = d.child_by_field_name('name'), d.child_by_field_name('value')
                        source = _require(value)
                        if name is not None and name.type == 'identifier' and source:
                            self._imports[common.text(name)] = (source, 'default')
        return self._imports

    def _import_statement(self, node):
        source = node.child_by_field_name('source')
        clause = next((c for c in node.named_children if c.type == 'import_clause'), None)
        if source is None or clause is None:
            return
        src = common.string_value(source)
        for c in clause.named_children:
            if c.type == 'identifier':
                self._imports[common.text(c)] = (src, 'default')
            elif c.type == 'named_imports':
                for spec in c.named_children:
                    name, alias = spec.child_by_field_name('name'), spec.child_by_field_name('alias')
                    if name is not None:
                        self._imports[common.text(alias or name)] = (src, common.text(name))

    def default_export(self):
        for child in self.root.named_children:
            if child.type == 'export_statement':
                value = child.child_by_field_name('value')
                if value is not None and value.type == 'identifier':
                    return common.text(value)
            elif child.type == 'expression_statement':
                e = child.named_children[0] if child.named_children else None
                if e is not None and e.type == 'assignment_expression':
                    left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
                    if common.text(left) == 'module.exports' and right.type == 'identifier':
                        return common.text(right)
        return None


# ---- prefixes across files ----------------------------------------------------------------------------------------


def _mounted_routes(repo, files):
    """Routes with the prefixes of every `use('/prefix', router)` that mounts their router, nested up to MAX_DEPTH."""
    by_path = {f.path: f for f in files}
    parents = {}  # (file, receiver) -> [(parent key, prefix)]
    for f in files:
        for parent, prefix, child in f.mounts:
            target = _mount_target(f, child, by_path)
            if target is not None:
                parents.setdefault(target, []).append(((f.path, parent), prefix))

    def prefixes(key, seen):
        found = parents.get(key, []) + parents.get((key[0], '*'), [])
        found = [(parent, prefix) for parent, prefix in found if parent not in seen]  # a router mounted in itself
        if not found or len(seen) > MAX_DEPTH:
            return ['']
        return [p + prefix for parent, prefix in found for p in prefixes(parent, seen | {parent})]

    out = []
    for f in files:
        for receiver, path, methods, handler, line in f.routes:
            key = (f.path, receiver)
            for prefix in sorted(set(prefixes(key, {key}))):
                full = (prefix.rstrip('/') + '/' + path.lstrip('/')) if prefix else path
                tpl = PathTemplate.parse(express_path(full))
                out.append(Route(repo, f.path, line, tpl, methods, handler, framework=FRAMEWORK))
    return out


def _mount_target(f, child, by_path):
    """The (file, router name) a mounted expression stands for; router name '*' means every route of that file."""
    if child.type == 'identifier':
        name = common.text(child)
        imported = f.imports().get(name)
        if imported is None:
            return (f.path, name)
        source, member = imported
    else:
        source, member = _require(child), 'default'
        if not source:
            return None
    target = _resolve_module(f.path, source, by_path)
    if target is None:
        return None
    if member != 'default':
        return (target.path, member)
    return (target.path, target.default_export() or '*')


def _resolve_module(path, source, by_path):
    if not source.startswith('.'):
        return None
    base = os.path.normpath(os.path.join(os.path.dirname(path), source)).replace(os.sep, '/')
    base = re.sub(r'\.(js|mjs|cjs)$', '', base)
    for stem in (base, base + '/index'):
        for ext in MODULE_EXTS:
            if stem + ext in by_path:
                return by_path[stem + ext]
    return None


# ---- helpers ------------------------------------------------------------------------------------------------------

_QUERIES = {}


def _query(lang):
    q = _QUERIES.get(id(lang))
    if q is None:
        q = _QUERIES[id(lang)] = ts.Query(lang, QUERY)
    return q


def express_path(path):
    """Express/Koa/Fastify/Hono path syntax to the canonical one: ':id' -> {id}, '*' -> {*rest}."""
    out = []
    for seg in path.split('/'):
        if seg in ('*', '(.*)', '(.*)?'):
            seg = '{*rest}'
        elif seg.startswith('*'):
            seg = '{*' + (re.sub(r'\W', '', seg) or 'rest') + '}'
        else:
            # ':id', ':id?', ':id(\\d+)', Hono's ':id{[0-9]{1,3}}' (one level of nested braces)
            seg = re.sub(r':(\w+)(\{(?:[^{}]|\{[^{}]*\})*\}|\([^)]*\))?\??', r'{\1}', seg)
            if '*' in seg:
                seg = '{*rest}'
        out.append(seg)
    joined = '/'.join(out)
    return joined if joined.startswith('/') else '/' + joined


def _method_set(verb):
    v = (verb or '').lower()
    if v == 'all' or not v:
        return frozenset({ANY})
    return frozenset({'DELETE' if v == 'del' else v.upper()})


def _unwrap(node):
    while node is not None and node.named_children and node.type in WRAPPERS | {'type_assertion'}:
        node = node.named_children[-1] if node.type == 'type_assertion' else node.named_children[0]
    return node


def _args(call):
    a = call.child_by_field_name('arguments')
    if a is None or a.type != 'arguments':
        return []
    return [x for x in a.named_children if x.type != 'comment']


def _prop(obj, key):
    """The value of `key` in an object literal."""
    obj = _unwrap(obj)
    if obj is None or obj.type != 'object':
        return None
    for p in obj.named_children:
        if p.type == 'pair':
            k = p.child_by_field_name('key')
            name = common.string_value(k) if k.type == 'string' else common.text(k)
            if name == key:
                return p.child_by_field_name('value')
        elif p.type == 'shorthand_property_identifier' and common.text(p) == key:
            return p
    return None


def _option_method(f, options, default):
    """The `method` of a request options object (literal, or a const bound to one); ANY when it is not a literal."""
    if options is None:
        return default
    options = _unwrap(options)
    if options.type == 'identifier':
        options = _unwrap(f._lookup(options, common.text(options)))
        if options is None:
            return default
    if options.type != 'object':
        return default
    method = _prop(options, 'method')
    if method is None:
        return default
    method = _unwrap(method)
    if method.type == 'string':
        return (common.string_value(method) or default).upper()
    return ANY


def _require(node):
    node = _unwrap(node)
    if node is None or node.type != 'call_expression':
        return None
    if common.text(node.child_by_field_name('function')) != 'require':
        return None
    args = _args(node)
    return common.string_value(_unwrap(args[0])) if args and _unwrap(args[0]).type == 'string' else None


def _last_name(node):
    """The name a receiver ends in, read from the tree: `this.apiClient` -> 'apiClient', `request(app)` -> 'request'."""
    for _ in range(MAX_DEPTH):
        node = _unwrap(node)
        if node is None:
            return ''
        if node.type == 'call_expression':
            node = node.child_by_field_name('function')
        elif node.type == 'member_expression':
            return common.text(node.child_by_field_name('property'))
        elif node.type in ('identifier', 'property_identifier', 'this'):
            return common.text(node)
        else:
            return ''
    return ''


def _words(name):
    """'QUERY_API_CLIENT' / 'routeMap' -> lower-case words."""
    spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name)
    return [w for w in re.split(r'[^a-z0-9]+', spaced.lower()) if w]


def _is_client(obj):
    """The receiver's last name ends like an HTTP client's: `api`, `this.apiClient`, `request(app)`, `axios`."""
    return bool(CLIENT.search(_last_name(obj)))


def _pattern_names(node):
    """Names a parameter or pattern binds (not the names in its default values)."""
    if node is None:
        return []
    if node.type in ('required_parameter', 'optional_parameter'):
        node = node.child_by_field_name('pattern')
    elif node.type in ('assignment_pattern', 'object_assignment_pattern'):
        node = node.child_by_field_name('left')
    elif node.type == 'pair_pattern':
        node = node.child_by_field_name('value')
    if node is None:
        return []
    if node.type in ('identifier', 'shorthand_property_identifier_pattern'):
        return [common.text(node)]
    if node.type in ('object_pattern', 'array_pattern', 'rest_pattern'):
        return [n for c in node.named_children for n in _pattern_names(c)]
    return []


def _returns(fn):
    """The function returns something: an arrow function's expression body or a `return` statement."""
    body = fn.child_by_field_name('body')
    return body is not None and (body.type != 'statement_block' or any(common.walk(body, {'return_statement'})))


def _first_type(node):
    """The first type name in a type annotation: `: Client` -> 'Client'."""
    for n in common.walk(node, {'type_identifier'}) if node is not None else ():
        return common.text(n)
    return ''


def _param_type(param, name):
    """The type of `name` in a parameter: `api: Client`, or `{api}: {api: Client}` for a destructured one."""
    if param.type not in ('required_parameter', 'optional_parameter'):
        return ''
    pattern, annotation = param.child_by_field_name('pattern'), param.child_by_field_name('type')
    if pattern is not None and pattern.type == 'identifier':
        return _first_type(annotation)
    for n in common.walk(annotation, {'property_signature'}) if annotation is not None else ():
        if common.text(n.child_by_field_name('name')) == name:
            return _first_type(n.child_by_field_name('type'))
    return ''


def _typed(type_name):
    return ('class', type_name) if type_name else None


def _join(left, right, right_node):
    """left + right for URL templates. A path held in a variable glued to a literal ('/api/0' + apiUrl) is a tail."""
    if (
        left
        and left[-1] not in '/}'
        and re.fullmatch(r'\{[^{}*]+\}', right or '')
        and PATH_NAME.search(common.text(right_node))
    ):
        return left + '/{*' + right[1:]
    return left + right


def _literal(value):
    return bool(re.sub(r'\{[^{}]*\}', '', value or ''))


def _path_like(value):
    """'/x', 'http://h/x', or '{BASE}/x' where the leading variable is a base URL."""
    if value.startswith('/') or '://' in value:
        return True
    m = re.match(r'^\{([^{}]*)\}/', value)
    return bool(m) and (bool(BASE_NAME.search(m.group(1))) or m.group(1).isupper())


def _contains(outer, inner):
    return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte


def _names_in(node):
    """Identifiers and member chains in a URL expression ('settings.API_URL', 'BASE')."""
    out = set()
    for n in common.walk(node, {'identifier', 'member_expression'}):
        if n.parent is not None and n.parent.type == 'member_expression':
            continue
        out.add(common.text(n))
    return out


def _member_values(node, field):
    """What `this.field` is set to, from the nearest enclosing class or object literal that sets it."""
    container = common.ancestor(node, CLASSES | {'object'})
    while container is not None:
        found = _field_values(container, field)
        if found:
            return found
        container = common.ancestor(container, CLASSES | {'object'})
    return []


def _field_values(container, field):
    """Initializers of `field` in a class (`field = ...`) or object literal (`field: ...`), or `this.field = ...`."""
    if container.type == 'object':
        body, members = container, [p for p in container.named_children if p.type == 'pair']
    else:
        body = container.child_by_field_name('body')
        if body is None:
            return []
        members = [m for m in body.named_children if m.type in ('field_definition', 'public_field_definition')]
    out = []
    for m in members:
        name = m.child_by_field_name('name') or m.child_by_field_name('property') or m.child_by_field_name('key')
        value = m.child_by_field_name('value')
        if value is not None and common.text(name) == field:
            out.append(value)
    for n in common.walk(body, {'assignment_expression'}):
        if common.text(n.child_by_field_name('left')) == 'this.' + field:
            out.append(n.child_by_field_name('right'))
    return out


def _function_name(fn):
    name = fn.child_by_field_name('name')
    if name is not None:
        return common.text(name)
    parent = fn.parent
    while parent is not None and parent.type in WRAPPERS:
        parent = parent.parent
    if parent is None:
        return ''
    if parent.type == 'variable_declarator':
        return common.text(parent.child_by_field_name('name'))
    if parent.type == 'pair':
        return common.text(parent.child_by_field_name('key'))
    if parent.type == 'assignment_expression':
        return common.text(parent.child_by_field_name('left')).split('.')[-1]
    if parent.type in ('field_definition', 'public_field_definition'):
        return common.text(parent.child_by_field_name('name') or parent.child_by_field_name('property'))
    return ''


def _enclosing(node):
    """(nearest named function, enclosing class name); anonymous callbacks are skipped."""
    function = ''
    n = node.parent
    while n is not None and not function:
        if n.type in FUNCTIONS:
            function = _function_name(n)
        n = n.parent
    cls = common.ancestor(node, CLASSES)
    name = cls.child_by_field_name('name') if cls is not None else None
    return function, common.text(name)


def _callee_head(fn):
    """The leftmost name of a callee: `describe.each([...])` -> 'describe'; '' for a function expression."""
    for _ in range(MAX_DEPTH):
        if fn is None:
            return ''
        if fn.type == 'identifier':
            return common.text(fn)
        if fn.type == 'member_expression':
            fn = fn.child_by_field_name('object')
        elif fn.type == 'call_expression':
            fn = fn.child_by_field_name('function')
        else:
            return ''
    return ''


def _in_test(node):
    n = node.parent
    while n is not None:
        if n.type == 'call_expression' and _callee_head(n.child_by_field_name('function')) in TEST_FUNCS:
            return True
        n = n.parent
    return False
