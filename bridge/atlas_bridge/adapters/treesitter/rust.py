"""rust: HTTP routes (axum, actix-web) and requests (reqwest/hyper clients, request-trait impls) via tree-sitter.

Routes are found by evaluating router expressions: `.route(path, method_router)` chains, `.nest(prefix, r)`,
`.merge(r)`, let-bound routers and functions in the crate that return routers, resolved by module and fn name.
Only routers nobody else nests or merges are emitted as roots, so nested routes carry their prefixes.

Requests come from two idioms: a type implementing a request trait whose `fn path` (or url/endpoint) yields a
literal, and `client.get(url)` / `.request(Method::X, url)` / `Request::new(Method::X, url)` calls.
"""

import bisect
import functools
import os
import re

import tree_sitter as ts

from ...core.http import ANY, Call, Extraction, PathTemplate, Route
from .common import (
    ancestor,
    is_test_path,
    language,
    line,
    parse,
    placeholder,
    read,
    split_url,
    string_value,
    text,
    walk,
)

VERBS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace', 'connect'}
CLIENT_VERBS = {'get', 'post', 'put', 'patch', 'delete', 'head'}
ROUTER_STEPS = {'route', 'nest', 'merge', 'route_service', 'nest_service', 'service', 'configure'}
PATH_FNS = {'path', 'url', 'endpoint'}
TRANSPARENT = {'parenthesized_expression', 'try_expression', 'reference_expression', 'await_expression'}
PASS_METHODS = {'clone', 'to_string', 'to_owned', 'into', 'as_str', 'as_ref', 'unwrap', 'expect', 'into_owned'}
PASS_FNS = {'from', 'parse', 'from_static', 'Borrowed', 'Owned', 'try_from', 'from_str', 'Some', 'Ok'}
STATEMENTS = {'expression_statement', 'let_declaration', 'line_comment', 'block_comment', 'attribute_item'}
BRANCHING = {'block', 'expression_statement', 'match_expression', 'if_expression'}
MAX_DEPTH = 5  # let/const hops when resolving a value
MAX_NESTING = 100  # expression nesting followed before giving up, far below Python's recursion limit
MAX_LEAVES = 64  # branches (match arms, if/else) of one expression
MAX_ROUTER_DEPTH = 32  # nested routers, or wrappers around a method router; cycles are caught separately

_CLIENT = re.compile(r'client|http|reqwest|request|upstream', re.I)
_METHOD = re.compile(r'(?:^|::)Method::([A-Z]+)$')
_FILTER = re.compile(r'MethodFilter::([A-Z]+)')
_ANY_METHOD = re.compile(r'\bMethod::([A-Z]+)\b')
_FMT = re.compile(r'\{\{|\}\}|\{([^{}]*)\}')
_TEST_DIR = re.compile(r'(^|[-_])(tests?|testutils|mocks?)($|[-_])')
_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+')
_GENERIC = re.compile(r'<[^<>]*>')
# a server bound to an ephemeral loopback port is an in-process mock or helper, not a service's API
_LOOPBACK = re.compile(r'\[127,0,0,1\],0\)|"(?:127\.0\.0\.1|localhost|\[::1\]):0"|Ipv[46]Addr::LOCALHOST\)?,0\)')

_QUERY_SRC = """
(function_item) @fn
(call_expression) @call
(impl_item) @impl
(attribute_item) @attr
(const_item) @const
(static_item) @const
(use_declaration) @use
"""


@functools.cache
def _query():
    return ts.Query(language('rust'), _QUERY_SRC)


def _key(f, node):
    return (f.path, node.start_byte, node.end_byte, node.type)


def _unwrap(node):
    while node is not None and node.type in TRANSPARENT:
        node = node.child_by_field_name('value') or (node.named_children[0] if node.named_children else None)
    return node


def _args(call):
    a = call.child_by_field_name('arguments')
    return [c for c in a.named_children if 'comment' not in c.type] if a is not None else []


def _strip_generics(s):
    """'Foo<Option<T>>' -> 'Foo'."""
    while '<' in s:
        stripped = _GENERIC.sub('', s)
        if stripped == s:
            break
        s = stripped
    return s


def _segments(fn_node):
    """'a::b::<T>::c' -> ['a', 'b', 'c']."""
    return [s for s in _strip_generics(text(fn_node)).split('::') if s]


def _camel(name):
    words = _CAMEL.findall(name)
    return ' '.join(words) if len(words) > 1 else ''


def _attributes(node):
    """Texts of the outer attributes right before an item."""
    out, n = [], node.prev_named_sibling
    while n is not None and n.type in ('attribute_item', 'line_comment', 'block_comment'):
        if n.type == 'attribute_item':
            out += [text(a) for a in n.named_children if a.type == 'attribute']
        n = n.prev_named_sibling
    return out


def _top_level_args(s):
    """'a,b(c,d),e' -> ['a', 'b(c,d)', 'e']."""
    out, cur, depth = [], '', 0
    for ch in s:
        depth += (ch == '(') - (ch == ')')
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    return out + [cur]


def _is_test_attr(attr):
    """#[test], #[tokio::test(..)], #[rstest], #[test_case(..)], #[cfg(test)], #[cfg(all(test, ..))]."""
    a = re.sub(r'\s', '', attr)
    if a.startswith('cfg('):
        if a == 'cfg(test)':
            return True
        m = re.fullmatch(r'cfg\(all\((.*)\)\)', a)
        return m is not None and 'test' in _top_level_args(m.group(1))
    name = a.split('(')[0]
    return name in ('test', 'rstest', 'test_case') or name.endswith(('::test', '_test'))


def _canonical(path):
    """axum/actix route syntax -> canonical: ':x' and '{x:re}' -> {x}, '*x' and '{x}*' -> {*x}."""
    segs = []
    for s in path.split('/'):
        if s.startswith(':'):
            s = '{' + s[1:] + '}'
        elif s.startswith('*') and len(s) > 1:
            s = '{*' + s[1:] + '}'
        elif re.fullmatch(r'\{[^{}]*\}\*', s):
            s = '{*' + s[1:-2].split(':')[0] + '}'
        elif re.fullmatch(r'\{[^{}*]*:[^{}]*\}', s):
            s = '{' + s[1:].split(':')[0] + '}'
        segs.append(s)
    return '/'.join(segs)


def _join(prefix, path):
    rest = path.strip('/')
    return prefix.rstrip('/') + ('/' + rest if rest else '') or '/'


def _param(expr):
    """A parameter name for an interpolated expression, skipping conversions: '&id.to_string()' -> 'id'."""
    words = [w for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr) if w not in PASS_METHODS]
    return placeholder(words[-1] if words else expr)


def _path_like(v):
    return v.startswith('/') or '://' in v or bool(re.match(r'^\{[^{}]*\}/', v))


class _File:
    def __init__(self, path, src, tree):
        self.path, self.src, self.root = path, src, tree.root_node
        stem = os.path.splitext(os.path.basename(path))[0]
        self.module = os.path.basename(os.path.dirname(path)) if stem in ('mod', 'lib', 'main') else stem
        self.parts = set(re.split(r'[/\\]', os.path.splitext(path)[0]))
        self.framework = 'axum'  # 'actix' when the file uses actix_web (set while indexing)
        dirs = path.replace('\\', '/').split('/')[:-1]
        self.testish = is_test_path(path) or any(_TEST_DIR.search(d) for d in dirs)
        self.file_test = False
        self.uses = {}  # local name -> full path ('axum_head' -> 'axum::routing::head')
        self.caps = {}
        self.outer = {}  # call key -> the call made on its result: `a()` -> `a().b()`

    def span(self, a, b):
        return self.src[a.start_byte : b.end_byte].decode('utf-8', 'replace')


def _use_tree(node, out):
    """Record the names a use declaration's argument brings in: {local name: full path}."""
    stack = [(node, '')]
    while stack:
        node, prefix = stack.pop()
        t = node.type
        if t == 'use_as_clause':
            path = prefix + _strip_generics(text(node.child_by_field_name('path')))
            out[text(node.child_by_field_name('alias'))] = path
        elif t == 'scoped_use_list':
            p = node.child_by_field_name('path')
            lst = node.child_by_field_name('list')
            if lst is not None:
                stack.append((lst, prefix + (text(p) + '::' if p is not None else '')))
        elif t == 'use_list':
            stack += [(c, prefix) for c in node.named_children]
        elif t in ('scoped_identifier', 'identifier'):
            full = prefix + text(node)
            out[full.split('::')[-1]] = full


class _Rust:
    def __init__(self, repo, files):
        self.repo, self.files = repo, files
        self.fns = {}  # name -> [(file, fn node)]
        self.consts = {}  # name -> [(file, value node)]
        self.attr_routes = {}  # fn key -> [(path, methods, line, file, fn node)] from #[get("/p")] macros
        self.memo, self.active = {}, set()
        self.consumed, self.consumed_fns = set(), set()
        self.lets = {}  # function key -> {name: ([let start], [(let node, enclosing block)])}
        self.loopback = {}  # function key -> whether it serves on an ephemeral loopback port
        self.nesting = 0
        for f in files:
            self._index(f)

    # ---------------------------------------------------------------- index

    def _index(self, f):
        f.caps = ts.QueryCursor(_query()).captures(f.root)
        for u in f.caps.get('use', []):
            arg = u.child_by_field_name('argument')
            if arg is not None:
                _use_tree(arg, f.uses)
                if text(arg).lstrip(':').startswith('actix'):
                    f.framework = 'actix'
        for c in f.caps.get('call', []):
            fn = c.child_by_field_name('function')
            if fn is not None and fn.type == 'field_expression':
                value = _unwrap(fn.child_by_field_name('value'))
                if value is not None and value.type == 'call_expression':
                    f.outer[_key(f, value)] = c
        for fn in f.caps.get('fn', []):
            parent = fn.parent
            if (
                parent is not None
                and parent.type == 'declaration_list'
                and parent.parent.type in ('impl_item', 'trait_item')
            ):
                continue
            self.fns.setdefault(text(fn.child_by_field_name('name')), []).append((f, fn))
        for c in f.caps.get('const', []):
            v = c.child_by_field_name('value')
            if v is not None:
                self.consts.setdefault(text(c.child_by_field_name('name')), []).append((f, v))
        for a in f.root.named_children:
            if a.type == 'inner_attribute_item' and any(_is_test_attr(text(x)) for x in a.named_children):
                f.file_test = True
        for a in f.caps.get('attr', []):
            self._attr_route(f, a)

    def _attr_route(self, f, attr_item):
        attr = next((c for c in attr_item.named_children if c.type == 'attribute'), None)
        if attr is None or not attr.named_children:
            return
        name = text(attr.named_children[0]).split('::')[-1]
        args = attr.child_by_field_name('arguments')
        if name not in VERBS | {'route'} or args is None:
            return
        lits = [string_value(c) for c in args.named_children if c.type in ('string_literal', 'raw_string_literal')]
        if not lits or not lits[0].startswith('/'):
            return
        methods = {name.upper()}
        if name == 'route':  # #[route("/p", method = "GET", method = "HEAD")]
            methods = {m.upper() for m in lits[1:] if m.isalpha()} or {ANY}
        fn = attr_item.next_named_sibling
        while fn is not None and fn.type in ('attribute_item', 'line_comment', 'block_comment'):
            fn = fn.next_named_sibling
        if fn is not None and fn.type == 'function_item':
            self.attr_routes.setdefault(_key(f, fn), []).append((_canonical(lits[0]), methods, line(attr_item), f, fn))

    def module_of(self, f, fn):
        m = ancestor(fn, ('mod_item',))
        return text(m.child_by_field_name('name')) if m is not None else f.module

    def resolve_fn(self, f, fnode):
        """The crate function a call's function expression names, as (file, fn node), or None."""
        if fnode is None or fnode.type not in ('identifier', 'scoped_identifier'):
            return None
        segs = _segments(fnode)
        if not segs:
            return None
        if segs[0] in f.uses:
            segs = f.uses[segs[0]].split('::') + segs[1:]
        name, mods = segs[-1], [s for s in segs[:-1] if s not in ('crate', 'self', 'super')]
        if mods and mods[-1][:1].isupper():  # Type::method: not a free function
            return None
        cands = self.fns.get(name, [])
        if mods:
            cands = [(cf, fn) for cf, fn in cands if self.module_of(cf, fn) == mods[-1]]
        if not cands:
            return None

        def rank(c):
            cf, _ = c
            return (cf is f, sum(m in cf.parts for m in mods), len(os.path.commonprefix([cf.path, f.path])))

        return max(cands, key=rank)

    def const_value(self, f, node):
        node = _unwrap(node)
        if node is None or node.type not in ('identifier', 'scoped_identifier'):
            return None
        cands = self.consts.get(_segments(node)[-1], [])
        if not cands:
            return None
        cf, v = max(cands, key=lambda c: c[0] is f)
        return cf, v

    # ------------------------------------------------------------ bindings

    def binding(self, f, node):
        """The value of the latest `let name = value` before `node` in its function, or None."""
        scope = ancestor(node, ('function_item',))
        if scope is None:
            return None
        starts, lets = self._lets(f, scope).get(text(node), ((), ()))
        pos = node.start_byte
        for i in range(bisect.bisect_left(starts, pos) - 1, -1, -1):
            let, block = lets[i]
            if let.end_byte <= pos and block.start_byte <= pos <= block.end_byte:  # in scope at `node`
                return let.child_by_field_name('value')
        return None

    def _lets(self, f, scope):
        """{name: ([start byte], [(let declaration, enclosing block)])} of a function, in source order."""
        k = _key(f, scope)
        if k not in self.lets:
            found = {}
            stack = [scope.child_by_field_name('body')]
            while stack:
                n = stack.pop()
                for c in n.named_children if n is not None else ():
                    pat, value = c.child_by_field_name('pattern'), c.child_by_field_name('value')
                    if c.type == 'let_declaration' and pat is not None and value is not None:
                        found.setdefault(text(pat).replace('mut ', '').strip(), []).append((c, n))
                    if c.type != 'function_item':
                        stack.append(c)
            index = {}
            for name, lets in found.items():
                lets.sort(key=lambda e: e[0].start_byte)
                index[name] = ([let.start_byte for let, _ in lets], lets)
            self.lets[k] = index
        return self.lets[k]

    @staticmethod
    def returns(fn):
        """The expressions a function returns: its tail expression and `return` values."""
        body = fn.child_by_field_name('body')
        out = []
        if body is None:
            return out
        tail = _tail(body)
        if tail is not None:
            out.append(tail)
        stack = list(body.named_children)
        while stack:
            n = stack.pop()
            if n.type == 'return_expression' and n.named_children:
                out.append(n.named_children[0])
            elif n.type not in ('function_item', 'closure_expression'):
                stack.extend(n.named_children)
        return out

    # -------------------------------------------------------------- routes

    def eval_router(self, f, node, depth=0):
        """Routes an expression yields: [(path, methods, handler, file, line)] relative to where it is mounted."""
        node = _unwrap(node)
        if node is None or depth > MAX_ROUTER_DEPTH:
            return []
        k = _key(f, node)
        if depth:
            self.consumed.add(k)
        if k in self.memo:
            return self.memo[k]
        if k in self.active:
            return []
        self.active.add(k)
        try:
            out = self._eval_router(f, node, depth)
        finally:
            self.active.discard(k)
        self.memo[k] = out
        return out

    def _eval_router(self, f, node, depth):
        t = node.type
        if t == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None and fn.type == 'field_expression':
                return self._chain(f, node, depth)
            return self._call_router(f, fn, depth)
        if t == 'identifier':
            value = self.binding(f, node)
            if value is not None:
                return self.eval_router(f, value, depth + 1)
            return self._fn_router(f, node, depth, call=False)
        out = []
        for branch in _branches(node):
            out += self.eval_router(f, branch, depth + 1)
        return out

    def _call_router(self, f, fn, depth):
        segs = _segments(fn) if fn is not None else []
        if not segs or segs[-1] in ('new', 'default'):
            return []
        return self._fn_router(f, fn, depth, call=True)

    def _fn_router(self, f, name_node, depth, call):
        hit = self.resolve_fn(f, name_node)
        if hit is None:
            return []
        cf, fn = hit
        self.consumed_fns.add(_key(cf, fn))
        attrs = self.attr_routes.get(_key(cf, fn))
        if attrs and not call:
            return [(p, m, text(fn.child_by_field_name('name')), af, ln) for p, m, ln, af, _ in attrs]
        out = []
        for r in self.returns(fn):
            out += self.eval_router(cf, r, depth + 1)
        return out

    def _chain(self, f, node, depth):
        steps = []
        while node is not None and node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                break
            steps.append((text(fn.child_by_field_name('field')), _args(node), node))
            node = _unwrap(fn.child_by_field_name('value'))
        steps.reverse()
        prefix = resource = None
        out = []
        if node is not None and node.type == 'call_expression':
            segs = _segments(node.child_by_field_name('function'))
            args = _args(node)
            last = segs[-1] if segs else ''
            if last in ('scope', 'resource') and args:
                value = self.path_value(f, args[0])
                if last == 'scope':
                    prefix = value
                else:
                    resource = value
            else:
                out = self.eval_router(f, node, depth + 1)
        elif node is not None:
            out = self.eval_router(f, node, depth + 1)
        for name, args, call in steps:
            out += self._step(f, name, args, call, resource, depth)
        if prefix is not None:
            out = [(_join(prefix, p), m, h, rf, ln) for p, m, h, rf, ln in out]
        return out

    def _step(self, f, name, args, call, resource, depth):
        ln = line(call.child_by_field_name('function').child_by_field_name('field'))
        if resource is not None:
            if name == 'route' and len(args) == 1:
                return [(resource, m, h, f, ln) for h, m in _by_handler(self.method_router(f, args[0]))]
            if name in ('to', 'to_async') and args:
                return [(resource, {ANY}, text(args[0]), f, ln)]
            if name in VERBS and len(args) == 1:
                return [(resource, {name.upper()}, text(args[0]), f, ln)]
        if name == 'route' and len(args) == 2:
            path = self.path_value(f, args[0])
            if path is None:
                return []
            return [(path, m, h, f, ln) for h, m in _by_handler(self.method_router(f, args[1]))]
        if name in ('route_service', 'nest_service') and len(args) == 2:
            path = self.path_value(f, args[0])
            if path is None:
                return []
            path = _join(path, '{*rest}') if name == 'nest_service' else path
            return [(path, {ANY}, text(args[1]), f, ln)]
        if name == 'nest' and len(args) == 2:
            prefix = self.path_value(f, args[0])
            if prefix is None:
                return []
            return [(_join(prefix, p), m, h, rf, rl) for p, m, h, rf, rl in self.eval_router(f, args[1], depth + 1)]
        if name in ('merge', 'service') and len(args) == 1:
            return self.eval_router(f, args[0], depth + 1)
        if name == 'configure' and len(args) == 1:
            return self._configure(f, args[0], depth)
        return []

    def _configure(self, f, node, depth):
        hit = self.resolve_fn(f, _unwrap(node))
        if hit is None:
            return []
        cf, fn = hit
        self.consumed_fns.add(_key(cf, fn))
        out = []
        body = fn.child_by_field_name('body')
        for st in body.named_children if body is not None else []:
            if st.type == 'expression_statement' and st.named_children:
                out += self.eval_router(cf, st.named_children[0], depth + 1)
        return out

    def path_value(self, f, node):
        node = _unwrap(node)
        if node is None:
            return None
        if node.type in ('string_literal', 'raw_string_literal'):
            return _canonical(string_value(node))
        hit = self.const_value(f, node)
        if hit is not None and hit[1].type in ('string_literal', 'raw_string_literal'):
            return _canonical(string_value(hit[1]))
        return None

    def method_router(self, f, node, depth=0):
        """{method: handler} of an axum method router (`get(h).post(g)`, `on(..)`, a factory fn) or actix route."""
        node = _unwrap(node)
        if node is None or node.type != 'call_expression' or depth > MAX_ROUTER_DEPTH:
            return {ANY: text(node)}
        fn = node.child_by_field_name('function')
        args = _args(node)
        first = text(args[0]) if args else ''
        if fn.type == 'field_expression':
            name = text(fn.child_by_field_name('field'))
            served = self.method_router(f, fn.child_by_field_name('value'), depth + 1)
            if name in VERBS:
                return _serve(served, {name.upper()}, first)
            if name == 'on' and len(args) == 2:
                return _serve(served, set(_FILTER.findall(first)) or {ANY}, text(args[1]))
            if name in ('to', 'to_async') and args:  # actix: web::post().to(handler)
                return dict.fromkeys(served, first)
            return served  # a layer or other wrapper
        segs = _segments(fn)
        local = segs[-1] if segs else ''
        name = f.uses.get(local, local).split('::')[-1] if len(segs) == 1 else local
        base = name[: -len('_service')] if name.endswith('_service') else name
        if base in VERBS:
            return {base.upper(): first}
        if base == 'any' or (base == 'route' and not args):
            return {ANY: first}
        if name == 'on' and len(args) == 2:
            return dict.fromkeys(set(_FILTER.findall(first)) or {ANY}, text(args[1]))
        if name == 'method' and args:
            return dict.fromkeys(set(_ANY_METHOD.findall(first)) or {ANY}, '')
        hit = self.resolve_fn(f, fn)
        k = hit and _key(*hit)
        if hit is None or k in self.active:
            return {ANY: text(fn)}
        self.active.add(k)
        served = {}
        try:
            cf, target = hit
            for r in self.returns(target):
                for m, h in self.method_router(cf, r, depth + 1).items():
                    served.setdefault(m, h)
        finally:
            self.active.discard(k)
        if not served:
            return {ANY: text(fn)}
        if len(served) > 1:
            served.pop(ANY, None)
        module = segs[:-1]  # handlers named in a factory live in its module: `store::route` -> `store::handle`
        return {m: '::'.join(module + [h]) if h and module else h or text(fn) for m, h in served.items()}

    def router_tops(self, f):
        """The outermost calls of the method chains in `f` that have a router step (`.route`, `.nest`, ...)."""
        for c in f.caps.get('call', []):
            if _key(f, c) in f.outer:
                continue  # not the outermost call of its chain
            n = c
            while n is not None and n.type == 'call_expression':
                fn = n.child_by_field_name('function')
                if fn is None or fn.type != 'field_expression':
                    break
                if text(fn.child_by_field_name('field')) in ROUTER_STEPS:
                    if not self.in_test(c) and not self.serves_loopback(f, c):
                        yield c
                    break
                n = _unwrap(fn.child_by_field_name('value'))

    def serves_loopback(self, f, node):
        """Whether the function around `node` binds an ephemeral loopback port: a local mock server."""
        fn = ancestor(node, ('function_item',))
        if fn is None:
            return False
        k = _key(f, fn)
        if k not in self.loopback:
            self.loopback[k] = bool(_LOOPBACK.search(re.sub(r'\s', '', text(fn))))
        return self.loopback[k]

    def routes(self):
        tops = []
        for f in self.files:
            if not (f.testish or f.file_test) and (b'Router' in f.src or b'actix' in f.src):
                tops += [(f, top) for top in self.router_tops(f)]
        results = [(f, top, _guarded(self.eval_router, f, top)) for f, top in tops]
        out, seen = [], set()

        def emit(path, methods, handler, rf, ln, framework=None):
            template = PathTemplate.parse(path)
            # no line in the key: trailing-slash variants registered on their own lines are one route
            k = (rf.path, str(template), frozenset(methods), handler)
            if k in seen:
                return
            seen.add(k)
            out.append(
                Route(
                    self.repo, rf.path, ln, template, frozenset(methods), handler, framework=framework or rf.framework
                )
            )

        for f, top, routes in results:
            if _key(f, top) in self.consumed:
                continue
            fn = ancestor(top, ('function_item',))
            if fn is not None and _key(f, fn) in self.consumed_fns:
                continue
            for r in routes:
                emit(*r)
        for k, attrs in self.attr_routes.items():
            if k in self.consumed_fns:
                continue
            for path, methods, ln, af, fn in attrs:
                if not af.testish and not af.file_test and not self.in_test(fn):
                    emit(path, methods, text(fn.child_by_field_name('name')), af, ln, 'actix')
        return out

    # --------------------------------------------------------------- calls

    def in_test(self, node):
        n = node
        while n is not None:
            if n.type in ('function_item', 'mod_item', 'impl_item') and any(map(_is_test_attr, _attributes(n))):
                return True
            n = n.parent
        return False

    def values(self, f, node, depth=MAX_DEPTH, join=False):
        """String values an expression can yield: [(template, node, base hints)]. Format args become {name}."""
        node = _unwrap(node)
        if node is None or depth < 0 or self.nesting >= MAX_NESTING:
            return []
        self.nesting += 1
        try:
            return self._values(f, node, depth, join)
        finally:
            self.nesting -= 1

    def _values(self, f, node, depth, join):
        t = node.type
        if t in ('string_literal', 'raw_string_literal'):
            return [(string_value(node), node, [])]
        if t == 'macro_invocation':
            if text(node.child_by_field_name('macro')).split('::')[-1] in ('format', 'format_args'):
                v = self.format(f, node, join)
                return [v] if v else []
            return []
        if t == 'call_expression':
            return self._call_values(f, node, depth, join)
        if t in ('identifier', 'scoped_identifier', 'field_expression'):
            if t == 'identifier':
                value = self.binding(f, node)
                if value is not None:
                    return self.values(f, value, depth - 1, join)
            hit = self.const_value(f, node)
            if hit is not None:
                return self.values(hit[0], hit[1], depth - 1, join)
            return []
        if _is_concat(node):
            return self._concat(f, node, depth, join)
        out = []
        for leaf in _leaves(node) if t in BRANCHING else ():
            out += self.values(f, leaf, depth, join)
        return out

    def _concat(self, f, node, depth, join):
        """`base + "/x/" + &id`: known parts are kept, an unknown first part is the base, later ones {params}."""
        whole, operands = node, []
        while _is_concat(node):  # folded iteratively: `a + b + c` nests to the left
            operands.append(node.child_by_field_name('right'))
            node = _unwrap(node.child_by_field_name('left'))
        operands.append(node)
        operands.reverse()
        value, hints = None, []
        for i, part in enumerate(operands):
            found = self.values(f, part, depth, join or i > 0)
            if found:
                v, _, more = found[0]
                if value is not None:
                    value, hints = value + v, hints + more
                elif i:  # what came before is unknown: the base
                    value, hints = '{}' + v, [f.span(operands[0], operands[i - 1])] + more
                else:
                    value, hints = v, more
            elif value is not None:
                value += '{' + _param(text(part)) + '}'
        return [] if value is None else [(value, whole, hints)]

    def _call_values(self, f, node, depth, join):
        fn = node.child_by_field_name('function')
        args = _args(node)
        if fn.type == 'field_expression':
            name = text(fn.child_by_field_name('field'))
            recv = fn.child_by_field_name('value')
            if name in PASS_METHODS:
                return self.values(f, recv, depth, join)
            if name == 'join' and len(args) == 1:
                rel = self.values(f, args[0], depth, join=True)
                if not rel:
                    return []
                value, _, hints = rel[0]
                hints = hints + [text(recv)]
                if not _path_like(value):
                    base = self.values(f, recv, depth)
                    if base:
                        bv = base[0][0]
                        value = bv[: bv.rfind('/') + 1] + value if '/' in bv else bv + '/' + value
                        hints += base[0][2]
                    else:
                        value = '/' + value
                return [(value, node, hints)]
            return []
        segs = _segments(fn)
        if segs and segs[-1] in PASS_FNS and len(args) == 1:
            return self.values(f, args[0], depth, join)
        return []

    def format(self, f, macro, join=False):
        tt = next((c for c in macro.children if c.type == 'token_tree'), None)
        if tt is None:
            return None
        groups, cur = [], []
        for c in tt.children[1:-1]:
            if c.type == ',':
                groups.append(cur)
                cur = []
            else:
                cur.append(c)
        if cur:
            groups.append(cur)
        if not groups or len(groups[0]) != 1 or groups[0][0].type not in ('string_literal', 'raw_string_literal'):
            return None
        fmt = string_value(groups[0][0])
        positional, named = [], {}
        for g in groups[1:]:
            if not g:
                continue
            if len(g) >= 3 and g[1].type == '=' and g[0].type == 'identifier':
                named[text(g[0])] = f.span(g[2], g[-1])
            else:
                positional.append(f.span(g[0], g[-1]))
        out, pos, hints, index = '', 0, [], 0
        for m in _FMT.finditer(fmt):
            out += fmt[pos : m.start()]
            pos = m.end()
            if m.group(1) is None:
                continue  # '{{' or '}}': a literal brace, never part of a path
            name = m.group(1).split(':')[0].strip()
            if not name or (name.isascii() and name.isdigit()):
                i = int(name) if name else index
                index += 0 if name else 1
                expr = positional[i] if i < len(positional) else ''
            else:
                expr = named.get(name, name)
            if not out and not join:  # a leading placeholder holds the scheme and host: the base
                hints.append(expr)
                out += '{}'
            else:
                out += '{' + _param(expr) + '}'
        out += fmt[pos:]
        return out, macro, hints

    def calls(self):
        out = []
        for f in self.files:
            for impl in f.caps.get('impl', []):
                out += _guarded(self.trait_calls, f, impl)
            for c in f.caps.get('call', []):
                call = _guarded(self.client_call, f, c)
                if call:
                    out.append(call)
        return out

    def trait_calls(self, f, impl):
        trait = impl.child_by_field_name('trait')
        body = impl.child_by_field_name('body')
        if trait is None or body is None:
            return []
        trait_name = _segments(trait)[-1] if _segments(trait) else text(trait)
        type_name = _strip_generics(text(impl.child_by_field_name('type'))).split('::')[-1]
        fns = {text(n.child_by_field_name('name')): n for n in body.named_children if n.type == 'function_item'}
        method, arm_methods = ANY, {}
        if 'method' in fns:
            method_body = fns['method'].child_by_field_name('body')
            found = set(_ANY_METHOD.findall(text(method_body)))
            method = found.pop() if len(found) == 1 else ANY
            arm_methods = _arm_methods(method_body)
        out = []
        test = f.testish or f.file_test or self.in_test(impl)
        for name in PATH_FNS & fns.keys():
            fn = fns[name]
            for r in self.returns(fn):
                for value, node, base in self.values(f, r):
                    path, more = split_url(value)
                    if path is None:
                        continue
                    hints = {trait_name, type_name, f.path, *base, *more} | {
                        h for h in map(_camel, (trait_name, type_name)) if h
                    }
                    arm = ancestor(node, ('match_arm', 'function_item'))  # `match self.kind`: method of the same arm
                    arm_key = _arm_key(arm) if arm is not None and arm.type == 'match_arm' else None
                    out.append(
                        Call(
                            self.repo,
                            f.path,
                            line(node),
                            PathTemplate.parse(path),
                            arm_methods.get(arm_key, method),
                            f'{type_name}::{name}',
                            frozenset(h for h in hints if h),
                            test=test,
                        )
                    )
        return out

    def client_call(self, f, c):
        fn = c.child_by_field_name('function')
        args = _args(c)
        if fn is None:
            return None
        method, url, recv = None, None, None
        if args and _METHOD.search(text(args[0])) and len(args) >= 2:
            method, url = _METHOD.search(text(args[0])).group(1), args[1]
            recv = fn.child_by_field_name('value') if fn.type == 'field_expression' else fn
        elif fn.type == 'field_expression' and len(args) == 1:
            name = text(fn.child_by_field_name('field'))
            if name not in CLIENT_VERBS:
                return None
            method, url, recv = name.upper(), args[0], fn.child_by_field_name('value')
        elif fn.type == 'field_expression' and len(args) == 2 and text(fn.child_by_field_name('field')) == 'request':
            method, url, recv = ANY, args[1], fn.child_by_field_name('value')
        elif fn.type == 'scoped_identifier' and len(args) == 1:
            segs = _segments(fn)
            if not (segs[-1] in CLIENT_VERBS and len(segs) > 1 and _CLIENT.search('::'.join(segs[:-1]))):
                return None
            method, url, recv = segs[-1].upper(), args[0], fn
        else:
            return None
        vals = self.values(f, url)
        if not vals:
            return None
        value, _, base = vals[0]
        if not _path_like(value) and not _CLIENT.search(_receiver_name(recv)):
            return None
        path, more = split_url(value)
        if path is None:
            return None
        hints = {text(recv), text(url), f.path, *base, *more}
        hints |= {text(n) for n in _identifiers(url)}
        hints |= self._context_hints(f, c, recv)
        return Call(
            self.repo,
            f.path,
            line(c),
            PathTemplate.parse(path),
            method,
            self._function_name(c),
            frozenset(h for h in hints if h and len(h) < 300),
            test=f.testish or f.file_test or self.in_test(c),
        )

    def _context_hints(self, f, c, recv):
        hints = set()
        impl = ancestor(c, ('impl_item',))
        if impl is not None:
            for field in ('type', 'trait'):
                n = impl.child_by_field_name(field)
                if n is not None:
                    hints.add(_strip_generics(text(n)))
        fn = ancestor(c, ('function_item',))
        if fn is not None:
            hints.add(text(fn.child_by_field_name('name')))
        root = _chain_root(recv)
        if root is not None and root.type == 'identifier':
            value = self.binding(f, root)
            if value is not None:
                hints.add(text(value))
            else:
                hit = self.const_value(f, root)
                if hit is not None:
                    hints.add(text(hit[1]))
        n = c  # what is done with the request after it is built: `.send_to(state.upstream_relay())`
        while _key(f, n) in f.outer:
            n = f.outer[_key(f, n)]
            hints.add(text(n.child_by_field_name('function').child_by_field_name('field')))
            for a in _args(n):
                hints |= {text(i) for i in _identifiers(a)}
        return hints

    @staticmethod
    def _function_name(node):
        fn = ancestor(node, ('function_item',))
        if fn is None:
            return ''
        name = text(fn.child_by_field_name('name'))
        impl = ancestor(fn, ('impl_item',))
        if impl is not None:
            return _strip_generics(text(impl.child_by_field_name('type'))).split('::')[-1] + '::' + name
        return name


def _tail(block):
    kids = [c for c in block.named_children if 'comment' not in c.type]
    if not kids:
        return None
    last = kids[-1]
    if last.type == 'expression_statement':
        return last if not text(last).rstrip().endswith(';') else None
    return None if last.type in STATEMENTS or last.type.endswith('_item') else last


def _branches(node):
    """The expressions a block-like expression evaluates to: a block's tail, every match arm, both if branches."""
    t = node.type
    if t == 'block':
        tail = _tail(node)
        return [tail] if tail is not None else []
    if t == 'expression_statement':
        return node.named_children[:1]
    if t == 'match_expression':
        body = node.child_by_field_name('body')
        arms = body.named_children if body is not None else []
        return [
            a.child_by_field_name('value') for a in arms if a.type == 'match_arm' and a.child_by_field_name('value')
        ]
    if t == 'if_expression':
        out = [node.child_by_field_name('consequence')]
        alt = node.child_by_field_name('alternative')
        if alt is not None:
            out += alt.named_children[:1]
        return [b for b in out if b is not None]
    return []


def _leaves(node):
    """The non-branching expressions a block, match or if/else chain can evaluate to, flattened iteratively."""
    out, stack = [], [node]
    while stack and len(out) < MAX_LEAVES:
        n = _unwrap(stack.pop())
        if n is None:
            continue
        if n.type in BRANCHING:
            stack += reversed(_branches(n))
        else:
            out.append(n)
    return out


def _is_concat(node):
    return node is not None and node.type == 'binary_expression' and text(node.child_by_field_name('operator')) == '+'


def _serve(served, methods, handler):
    """Add `methods -> handler` to a method router's map; an unresolved (ANY) receiver is replaced."""
    out = {} if set(served) == {ANY} else dict(served)
    out.update(dict.fromkeys(methods, handler))
    return out


def _by_handler(served):
    """{method: handler} -> [(handler, methods)]: one route per handler."""
    groups = {}
    for m, h in served.items():
        groups.setdefault(h, set()).add(m)
    return list(groups.items())


def _arm_key(arm):
    """A match arm's pattern, as the path it names: `Kind::Create { .. }` -> 'Kind::Create'."""
    pattern = re.sub(r'\s', '', text(arm.child_by_field_name('pattern')))
    m = re.match(r'[\w:]+', pattern)
    return m.group() if m else pattern


def _arm_methods(body):
    """{arm key: method} for the arms of a `match` in a request's `fn method` that each yield one Method::X."""
    out = {}
    for arm in walk(body, ('match_arm',)) if body is not None else ():
        found = set(_ANY_METHOD.findall(text(arm.child_by_field_name('value'))))
        if len(found) == 1:
            out[_arm_key(arm)] = found.pop()
    return out


def _guarded(fn, *args):
    """fn(*args), or [] when an absurdly nested input still exhausts the stack: one file must not stop the repo."""
    try:
        return fn(*args)
    except RecursionError:
        return []


def _chain_root(node):
    node = _unwrap(node)
    while node is not None:
        if node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                return fn
            node = _unwrap(fn.child_by_field_name('value'))
        elif node.type == 'field_expression':
            node = _unwrap(node.child_by_field_name('value'))
        else:
            return node
    return None


def _receiver_name(node):
    """The last name in a receiver: `self.client` -> 'client', `Client::new()` -> 'Client::new'."""
    node = _unwrap(node)
    while node is not None:
        if node.type == 'field_expression':
            return text(node.child_by_field_name('field'))
        if node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None and fn.type == 'field_expression':
                name = text(fn.child_by_field_name('field'))
                if name in ('unwrap', 'expect', 'build', 'clone', 'unwrap_or_default'):
                    node = _unwrap(fn.child_by_field_name('value'))
                    continue
                return name
            return text(fn)
        return text(node)
    return ''


def _identifiers(node):
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in ('identifier', 'field_identifier'):
            yield n
        stack.extend(n.children)


def extract(repo, root, paths):
    files = []
    for p in paths:
        src = read(root, p)
        if src is None:
            continue
        files.append(_File(p, src, parse('rust', src)))
    r = _Rust(repo, files)
    return Extraction(r.routes(), r.calls())
