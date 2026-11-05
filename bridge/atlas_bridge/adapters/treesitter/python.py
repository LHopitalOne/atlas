"""python: HTTP routes and requests in Python code.

Routes: Flask/FastAPI-style decorators (`@app.route`, `@router.get`, blueprints and routers with prefixes) and Django
URLconfs (`path` / `re_path` / `url` lists composed through `include` from the root URLconf).
Requests: verb calls on requests/httpx/aiohttp/session/client-like receivers, `.request(method, url)`, urllib3
`.urlopen(METHOD, path)` and `urllib.request.urlopen`. URLs are resolved through literals, f-strings, `.format`, `%`,
`+`, `urljoin`, local variables and module constants, and through the parameters of wrapper functions up to the
callers that supply them. Payloads: `reverse('route-name')` URLs handed to another service.
"""

import itertools
import posixpath
import re

import tree_sitter as ts

from ...core.http import ANY, Call, Extraction, PathTemplate, Route
from .common import ancestor, is_test_path, language, line, placeholder, read, split_url, text, walk

VERBS = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
HTTP_METHODS = frozenset(v.upper() for v in VERBS)
_CLIENT = re.compile(r'requests|httpx|aiohttp|session|client|http|pool|api|conn', re.I)
_NOT_CLIENT = re.compile(r'cache|(^|\.)request\.session$|\.session\[', re.I)  # caches, Django's request.session
_URLISH = re.compile(r'url|uri|base|host|server|endpoint|addr|upstream|origin|domain', re.I)
_TOOLING_DIRS = {'.github', '.circleci', '.buildkite', '.gitlab'}  # CI scripts, anywhere in the path
_TOOLING_ROOTS = {'bin', 'devenv', 'scripts', 'tools'}  # developer tooling at the repository root
_STOP = frozenset(VERBS) | {'request', 'urlopen', 'send', 'call', 'run', '__init__', '__call__', 'main', 'handle'}
_JOINS = {'urljoin', 'url_join'}
_PATH_JOINS = {'posixpath', 'os.path', 'path'}
MAX_ALTS = 4  # alternatives one expression may resolve to
MAX_ROUTE_ALTS = 8  # paths one URLconf entry may expand to
MAX_FORWARD = 4  # wrapper levels followed up to the caller that supplies the path
MAX_IMPORTS = 5
MAX_SITES = 200
MAX_SETTLES = 2000  # call sites one request may be settled at, over all its forwarding chains

LIT, PARAM, UNK = 'lit', 'param', 'unk'
_MARK = re.compile('\x00(\\w+)\x01')
_CHOICE = '\x02'  # a method that depends on a condition over the wrapper's parameters: '\x02<index>'
_CALL_NAME = re.compile(rb'([A-Za-z_]\w*)\(')
_LEAD = re.compile(r'^\{(\w*)\}(?=[^/])')  # a base placeholder glued to the path: '{base_url}ip/{addr}'
_FLASK_PARAM = re.compile(r'<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>')
_DOTSTAR = re.compile(r'(?<!\\)\.[*+]')
_QUANT = re.compile(r'(\*|\+|\?|\{\d*,?\d*\})[?+]?')
_ESCAPES = {'\\': '\\', "'": "'", '"': '"', 'n': '\n', 't': '\t', 'r': '\r', '\n': ''}

_QUERY = """
(call function: [(identifier) @fn (attribute attribute: (identifier) @fn)]
  (#any-of? @fn "urlopen" "request" "get" "post" "put" "patch" "delete" "head" "options" "reverse" "reverse_lazy"
   "register_blueprint" "include_router" "add_url_rule")) @call
(decorated_definition) @dec
(function_definition name: (identifier) @defname) @def
(class_definition name: (identifier) @clsname) @cls
"""
_CALLS = '(call) @call'


class _V:
    """One possible value of an expression: text with {placeholders}, parameter markers and a '{}' unknown base."""

    __slots__ = ('text', 'hints', 'kind')

    def __init__(self, text_, hints=frozenset(), kind=LIT):
        self.text = text_
        self.hints = hints
        self.kind = kind


class _Run:
    """One request's forwarding: whether its receiver is a client, the (function, values) already forwarded."""

    __slots__ = ('client', 'seen', 'settles')

    def __init__(self, client):
        self.client = client
        self.seen = set()
        self.settles = 0


class _File:
    __slots__ = ('path', 'src', 'tree', 'root', 'test', 'mod', 'lists', 'calls')

    def __init__(self, path, src, tree):
        self.path = path.replace('\\', '/')
        self.src = src
        self.tree = tree
        self.root = tree.root_node
        self.test = is_test_path(self.path) or _tooling(self.path)
        self.mod = None  # (assignments, functions, classes, imports) at module level
        self.lists = None  # module-level URL list contributions
        self.calls = None  # callee name -> call nodes


def extract(repo, root, paths):
    return _Extractor(repo, root, paths).run()


# ---------------------------------------------------------------------------------------------------- small helpers


def _mark(name):
    return f'\x00{name}\x01'


def _markers(s):
    return set(_MARK.findall(s))


def _tooling(path):
    parts = path.split('/')[:-1]
    return bool(parts) and (parts[0] in _TOOLING_ROOTS or any(p in _TOOLING_DIRS for p in parts))


def _render(s):
    """Markers as {name}; a base placeholder glued to the path gets its slash: '{}x' -> '{}/x'."""
    s = _MARK.sub(lambda m: '{' + m.group(1) + '}', s)
    m = _LEAD.match(s)
    if m and (not m.group(1) or _URLISH.search(m.group(1))):
        return s[: m.end()] + '/' + s[m.end() :]
    return s


def _base_ok(v, base):
    """Whether a value built on an unknown base still reads as a URL: '{}/path' or a base named like a URL."""
    return not v.text.startswith('{}') or v.text[2:3] in ('', '/', '?') or bool(_URLISH.search(base))


def _unescape(s):
    return re.sub(r'\\(.)', lambda m: _ESCAPES.get(m.group(1), m.group(0)), s, flags=re.S)


def _args(node):
    pos, kw = [], {}
    if node is None or node.type != 'argument_list':
        return pos, kw
    for a in node.named_children:
        if a.type == 'keyword_argument':
            kw[text(a.child_by_field_name('name'))] = a.child_by_field_name('value')
        elif a.type != 'comment':
            pos.append(a)
    return pos, kw


def _callee(call):
    fn = call.child_by_field_name('function')
    if fn is None:
        return ''
    if fn.type == 'attribute':
        return text(fn.child_by_field_name('attribute'))
    return text(fn) if fn.type == 'identifier' else ''


def _name(node):
    return text(node.child_by_field_name('name')) if node is not None else ''


def _targets(left, right):
    """[(name, value node)] an assignment binds; `a = b = value` binds both names (walked without recursion)."""
    lefts = []
    while left is not None and right is not None and right.type == 'assignment':
        lefts.append(left)
        left, right = right.child_by_field_name('left'), right.child_by_field_name('right')
    if lefts:
        inner = _targets(left, right)
        value = inner[-1][1] if inner else None
        outer = [(text(n), value) for n in reversed(lefts) if n.type == 'identifier' and value is not None]
        return inner + outer
    if left is None or right is None:
        return []
    if left.type == 'identifier':
        return [(text(left), right)]
    if left.type in ('pattern_list', 'tuple_pattern') and right.type in ('expression_list', 'tuple'):
        ls, rs = left.named_children, right.named_children
        if len(ls) == len(rs):
            return [(text(a), b) for a, b in zip(ls, rs, strict=True) if a.type == 'identifier']
    return []


def _docstring(block):
    """The docstring of a module or function body, or None."""
    first = block.named_children[0] if block is not None and block.named_children else None
    doc = first.named_children[0] if first is not None and first.type == 'expression_statement' else None
    return doc if doc is not None and doc.type == 'string' else None


def _module_statements(node):
    """Statements at module level, including those inside if/try/with blocks."""
    for c in node.children:
        if c.type in (
            'if_statement',
            'elif_clause',
            'else_clause',
            'try_statement',
            'except_clause',
            'finally_clause',
            'with_statement',
            'block',
        ):
            yield from _module_statements(c)
        else:
            yield c


def _body_nodes(node):
    """Every node under a function body, not descending into nested functions, classes or lambdas."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for c in reversed(n.children):
            if c.type not in ('function_definition', 'class_definition', 'lambda', 'decorated_definition'):
                stack.append(c)


def _params(func):
    """[(name, default node or None)] of a function's positional-or-keyword and keyword-only parameters."""
    out = []
    params = func.child_by_field_name('parameters')
    for p in params.named_children if params is not None else ():
        t = p.type
        if t == 'identifier':
            out.append((text(p), None))
        elif t == 'typed_parameter' and p.named_children and p.named_children[0].type == 'identifier':
            out.append((text(p.named_children[0]), None))
        elif t in ('default_parameter', 'typed_default_parameter'):
            out.append((text(p.child_by_field_name('name')), p.child_by_field_name('value')))
    return out


def _is_method(func):
    parent = func.parent
    decorators = []
    if parent is not None and parent.type == 'decorated_definition':
        decorators = [text(d) for d in parent.children if d.type == 'decorator']
        parent = parent.parent
    in_class = parent is not None and parent.type == 'block' and parent.parent.type == 'class_definition'
    return in_class and not any('staticmethod' in d for d in decorators)


def _flask_path(s):
    s = _FLASK_PARAM.sub(lambda m: '{*' + m.group(2) + '}' if m.group(1) == 'path' else '{' + m.group(2) + '}', s)
    s = re.sub(r'\{(\w+):path\}', r'{*\1}', s)
    return re.sub(r'\{(\w+):[^{}]*\}', r'{\1}', s)


def _pathlike(raw, base, client, literals):
    """Whether a URL value looks like a request path; a client-like receiver needs less evidence.

    On another receiver, an unknown base followed only by parameters ('{}/{db}', a cache key) is not enough.
    """
    if raw.startswith('/') or '://' in raw or base:
        return True
    if raw.startswith('{}/'):
        return client or literals >= 1
    return client and (raw.startswith('{}') or '/' in raw)


def _is_client(recv):
    t = text(recv)
    return bool(_CLIENT.search(t)) and not _NOT_CLIENT.search(t)


def _identifiers(node):
    return {text(n) for n in walk(node, ('identifier',))}


def _test_over(test, params):
    """Whether a condition reads only the function's parameters, so a call site's arguments can decide it."""
    names = _identifiers(test) if test is not None else set()
    return bool(names) and names <= params


def _argument(name, bound, defaults):
    """(known, node): the argument a call site binds to a parameter, else its default (node None: no value)."""
    if name in bound:
        return True, bound[name]
    if name in defaults:
        return defaults[name] is not None, defaults[name]
    return False, None


def _literal_truth(node):
    """Truth of an argument: literals by value; any other expression counts as a supplied, truthy value."""
    t = node.type
    if t in ('none', 'false'):
        return False
    if t in ('integer', 'float'):
        return text(node).strip('0.') != ''
    if t in ('string', 'concatenated_string', 'list', 'tuple', 'dictionary', 'set'):
        return any(c.type not in ('string_start', 'string_end') for c in node.named_children)
    return True


def _truth(node, bound, defaults):
    """A condition over parameters evaluated with one call site's arguments: True, False or None (unknown)."""
    t = node.type
    if t == 'parenthesized_expression' and node.named_children:
        return _truth(node.named_children[0], bound, defaults)
    if t == 'not_operator':
        v = _truth(node.child_by_field_name('argument'), bound, defaults)
        return None if v is None else not v
    if t == 'boolean_operator':
        a = _truth(node.child_by_field_name('left'), bound, defaults)
        b = _truth(node.child_by_field_name('right'), bound, defaults)
        if text(node.child_by_field_name('operator')) == 'and':
            return False if False in (a, b) else (True if a and b else None)
        return True if True in (a, b) else (False if a is False and b is False else None)
    if t == 'comparison_operator':
        kids = node.named_children
        op = next((c.type for c in node.children if not c.is_named), '')
        if len(kids) != 2 or kids[1].type != 'none' or kids[0].type != 'identifier' or op not in ('is', 'is not'):
            return None
        known, arg = _argument(text(kids[0]), bound, defaults)
        if not known:
            return None
        return (arg.type == 'none') != (op == 'is not')
    if t == 'identifier':
        known, arg = _argument(text(node), bound, defaults)
        return _literal_truth(arg) if known else None
    return None


# ------------------------------------------------------------------------------------------- regex -> path template


def _regex_templates(rx):
    """A Django regex as path templates (alternations expand): '^(?P<id>[^/]+)/(?:a|b)/?$' -> ['{id}/a', '{id}/b']."""
    alts, _ = _rx_seq(rx, 0)
    out = []
    for a in alts:
        if a not in out:
            out.append(a)
    return out[:MAX_ROUTE_ALTS] or ['']


def _rx_close(s, i):
    depth, j, cls = 0, i, False
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if cls:
            cls = c != ']'
        elif c == '[':
            cls = True
            if s[j + 1 : j + 2] == '^':
                j += 1
            if s[j + 1 : j + 2] == ']':
                j += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return len(s)


def _rx_class_end(s, i):
    j = i + 1
    if s[j : j + 1] == '^':
        j += 1
    if s[j : j + 1] == ']':
        j += 1
    while j < len(s):
        if s[j] == '\\':
            j += 2
            continue
        if s[j] == ']':
            return j
        j += 1
    return len(s)


def _rx_seq(s, i):
    branches, cur = [], ['']
    while i < len(s) and s[i] != ')':
        if s[i] == '|':
            branches += cur
            cur = ['']
            i += 1
            continue
        kind, opts, i = _rx_atom(s, i)
        m = _QUANT.match(s, i)
        if m:
            i = m.end()
            q = m.group(1)
            optional = q in ('?', '*') or q.startswith(('{0', '{,'))
            if kind == 'dot':
                opts = ['{*path}']
            elif kind == 'wild':
                opts = [''] if q == '?' else opts
            elif optional:
                opts = ['']
        cur = [a + b for a in cur for b in opts][:MAX_ROUTE_ALTS]
    return branches + cur, i


def _rx_atom(s, i):
    c = s[i]
    if c == '(':
        j = _rx_close(s, i)
        inner = s[i + 1 : j]
        if inner.startswith('?P<'):
            k = inner.find('>')
            name, body = inner[3:k], inner[k + 1 :]
            return 'wild', ['{*' + name + '}' if _DOTSTAR.search(body) else '{' + name + '}'], j + 1
        if inner.startswith('?:'):
            return 'group', _rx_seq(inner[2:], 0)[0], j + 1
        if inner.startswith('?P='):
            return 'wild', ['{param}'], j + 1
        if inner.startswith('?'):  # lookaround, inline flags, comment
            return 'lit', [''], j + 1
        return 'wild', ['{*param}' if _DOTSTAR.search(inner) else '{param}'], j + 1
    if c == '[':
        return 'wild', ['{param}'], _rx_class_end(s, i) + 1
    if c == '\\':
        n = s[i + 1 : i + 2]
        if n and n in 'dwsDWS':
            return 'wild', ['{param}'], i + 2
        if n and n in 'bBAZz':
            return 'lit', [''], i + 2
        return 'lit', [n], i + 2
    if c in '^$':
        return 'lit', [''], i + 1
    if c == '.':
        return 'dot', ['.'], i + 1
    return 'lit', [c], i + 1


# ------------------------------------------------------------------------------------------------------- extractor


class _Extractor:
    def __init__(self, repo, root, paths):
        self.repo = repo
        self.root = root
        self.paths = paths
        self.files = {}
        self.modindex = {}
        self.defs = {}  # function name -> [(file, node)]
        self.classes = {}  # class name -> [(file, node)]
        self.registrations = {}  # (file, blueprint/router node start) -> registered prefix
        self.routes = []
        self.calls = {}
        self._locals_cache = {}
        self._words_cache = {}
        self._attrs_cache = {}  # (file, class) -> (class attributes, self.attr assignments)
        self._mentions = None  # called name -> files, built on first use
        self._choices = []  # (function, condition, then, else) for methods decided per call site
        self._lang = language('python')

    # --------------------------------------------------------------------------------------------------- driver

    def run(self):
        parser = ts.Parser(self._lang)
        cursor = ts.QueryCursor(ts.Query(self._lang, _QUERY))
        calls, decs = [], []
        for p in self.paths:
            src = read(self.root, p)
            if src is None:
                continue
            f = _File(p, src, parser.parse(src))
            self.files[f.path] = f
            caps = cursor.captures(f.root)
            calls += [(f, c) for c in caps.get('call', ())]
            decs += [(f, d) for d in caps.get('dec', ())]
            for d in caps.get('def', ()):
                self.defs.setdefault(_name(d), []).append((f, d))
            for c in caps.get('cls', ()):
                self.classes.setdefault(_name(c), []).append((f, c))
        self._index_modules()
        rules = []
        for f, c in calls:
            name = _callee(c)
            if name in ('register_blueprint', 'include_router'):
                self._registration(f, c)
            elif name == 'add_url_rule':
                rules.append((f, c))
            elif name in ('reverse', 'reverse_lazy'):
                self._payload(f, c)
            else:
                self._request(f, c, name)
        for f, d in decs:
            self._decorated(f, d)
        for f, c in rules:
            self._url_rule(f, c)
        self._django()
        return Extraction(routes=self._unique_routes(), calls=list(self.calls.values()))

    def _unique_routes(self):
        seen, out = set(), []
        for r in self.routes:
            key = (r.file, r.line, str(r.path), r.methods, r.name)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return sorted(out, key=lambda r: (r.file, r.line, str(r.path)))

    # ---------------------------------------------------------------------------------------- modules and names

    def _index_modules(self):
        for path in self.files:
            parts = path[:-3].split('/')
            if parts[-1] == '__init__':
                parts = parts[:-1]
            for k in range(len(parts)):
                self.modindex.setdefault('.'.join(parts[k:]), []).append(path)
        for paths in self.modindex.values():
            paths.sort(key=lambda p: (is_test_path(p), len(p)))

    def _modfile(self, ref):
        kind, value = ref
        if kind == 'abs':
            paths = self.modindex.get(value)
            return self.files[paths[0]] if paths else None
        return self.files.get(value + '.py') or self.files.get(value + '/__init__.py')

    @staticmethod
    def _subref(ref, attr):
        return (ref[0], ref[1] + ('.' if ref[0] == 'abs' else '/') + attr)

    def _module(self, f):
        if f.mod is not None:
            return f.mod
        assigns, defs, classes, imports = {}, {}, {}, {}
        for st in _module_statements(f.root):
            t = st.type
            if t == 'decorated_definition':
                st = st.child_by_field_name('definition')
                t = st.type if st is not None else ''
            if t == 'expression_statement':
                for a in st.named_children:
                    if a.type == 'assignment':
                        for n, v in _targets(a.child_by_field_name('left'), a.child_by_field_name('right')):
                            assigns.setdefault(n, []).append((a.end_byte, v))
            elif t == 'function_definition':
                defs[_name(st)] = st
            elif t == 'class_definition':
                classes[_name(st)] = st
            elif t == 'import_statement':
                for n in st.named_children:
                    if n.type == 'aliased_import':
                        imports[text(n.child_by_field_name('alias'))] = (
                            ('abs', text(n.child_by_field_name('name'))),
                            None,
                        )
                    elif n.type == 'dotted_name':
                        top = text(n).split('.')[0]
                        imports[top] = (('abs', top), None)
            elif t == 'import_from_statement':
                ref = self._import_ref(f, st.child_by_field_name('module_name'))
                for n in st.children_by_field_name('name'):
                    if n.type == 'aliased_import':
                        imports[text(n.child_by_field_name('alias'))] = (ref, text(n.child_by_field_name('name')))
                    else:
                        imports[text(n)] = (ref, text(n))
        f.mod = (assigns, defs, classes, imports)
        return f.mod

    @staticmethod
    def _import_ref(f, mod):
        if mod is None or mod.type != 'relative_import':
            return ('abs', text(mod))
        prefix = next((c for c in mod.children if c.type == 'import_prefix'), None)
        dotted = next((c for c in mod.named_children if c.type == 'dotted_name'), None)
        base = posixpath.dirname(f.path)
        for _ in range(len(text(prefix)) - 1):
            base = posixpath.dirname(base)
        if dotted is not None:
            base = posixpath.join(base, *text(dotted).split('.'))
        return ('rel', base)

    def _lookup(self, f, name, depth=0, before=None):
        """What a module-level name means in a file: ('value'|'def'|'class', file, node) or ('module', ref).

        A value is the name's last assignment, or with `before` (a use at module level, which runs in order) the
        last one that ends before that byte, so `BASE = BASE + '/api'` reads the previous BASE.
        """
        if depth > MAX_IMPORTS:
            return None
        assigns, defs, classes, imports = self._module(f)
        assigned = assigns.get(name, ())
        values = [v for end, v in assigned if before is None or end <= before]
        if not values and before is not None:  # used above its assignment: take a later one, never its own
            values = [v for end, v in assigned if not v.start_byte <= before < end]
        if values:
            return ('value', f, values[-1])
        if name in defs:
            return ('def', f, defs[name])
        if name in classes:
            return ('class', f, classes[name])
        imp = imports.get(name)
        if imp is None:
            return None
        ref, attr = imp
        if attr is None:
            return ('module', ref)
        return self._member(ref, attr, depth + 1)

    def _member(self, ref, attr, depth):
        mf = self._modfile(ref)
        if mf is not None:
            found = self._lookup(mf, attr, depth)
            if found:
                return found
        sub = self._subref(ref, attr)
        return ('module', sub) if self._modfile(sub) is not None else None

    def _lookup_expr(self, f, node, depth=0):
        if node.type == 'identifier':
            return self._lookup(f, text(node), depth)
        if node.type == 'attribute' and depth <= MAX_IMPORTS:
            base = self._lookup_expr(f, node.child_by_field_name('object'), depth + 1)
            if base and base[0] == 'module':
                return self._member(base[1], text(node.child_by_field_name('attribute')), depth + 1)
        return None

    # ------------------------------------------------------------------------------------------------- scopes

    @staticmethod
    def _ctx(f, node):
        func = ancestor(node, ('function_definition',))
        cls = ancestor(func if func is not None else node, ('class_definition',))
        return (f, func, cls)

    @staticmethod
    def _qualified(ctx):
        _, func, cls = ctx
        if func is None:
            return ''
        return f'{_name(cls)}.{_name(func)}' if cls is not None else _name(func)

    def _locals(self, f, func):
        key = (f.path, func.start_byte)
        found = self._locals_cache.get(key)
        if found is None:
            found = {}
            for n in _body_nodes(func.child_by_field_name('body')):
                if n.type == 'assignment':
                    for name, v in _targets(n.child_by_field_name('left'), n.child_by_field_name('right')):
                        found.setdefault(name, []).append((n.end_byte, v, False))
                elif n.type == 'augmented_assignment' and text(n.child_by_field_name('operator')) == '+=':
                    left = n.child_by_field_name('left')
                    if left.type == 'identifier':
                        found.setdefault(text(left), []).append((n.end_byte, n.child_by_field_name('right'), True))
                elif n.type == 'named_expression':
                    found.setdefault(_name(n), []).append((n.end_byte, n.child_by_field_name('value'), False))
            for v in found.values():
                v.sort(key=lambda a: a[0])
            self._locals_cache[key] = found
        return found

    @staticmethod
    def _in_test(f, node):
        if f.test:
            return True
        n = node.parent
        while n is not None:
            if n.type == 'function_definition' and (_name(n).startswith('test_') or _name(n) == 'test'):
                return True
            if n.type == 'class_definition' and _name(n).startswith('Test'):
                return True
            n = n.parent
        return False

    # ------------------------------------------------------------------------------------------ value resolution

    def _unk(self, node):
        t = text(node)
        return _V('{' + placeholder(t) + '}', frozenset({t[:200]}), UNK)

    def _values(self, ctx, node, depth=0):
        if node is None:
            return [_V('{param}', frozenset(), UNK)]
        if depth > 14:
            return [self._unk(node)]
        t = node.type
        if t in ('string', 'concatenated_string'):
            return [self._string(ctx, node, depth)]
        if t == 'parenthesized_expression' and node.named_children:
            return self._values(ctx, node.named_children[0], depth + 1)
        if t == 'conditional_expression' and len(node.named_children) == 3:
            kids = node.named_children
            return (self._values(ctx, kids[0], depth + 1) + self._values(ctx, kids[2], depth + 1))[:MAX_ALTS]
        if t == 'identifier':
            return self._identifier(ctx, node, depth)
        if t == 'attribute':
            return self._attribute(ctx, node, depth)
        if t == 'binary_operator':
            op = node.child_by_field_name('operator').type
            if op == '+':
                return self._concat(ctx, node, depth)
            if op == '%':
                return self._percent(ctx, node, depth)
        if t == 'call':
            found = self._call_value(ctx, node, depth)
            if found:
                return found
        return [self._unk(node)]

    def _string(self, ctx, node, depth):
        if node.type == 'concatenated_string':
            parts = [self._string(ctx, c, depth) for c in node.named_children if c.type == 'string']
            return _V(''.join(p.text for p in parts), frozenset().union(*(p.hints for p in parts)), LIT)
        start = node.children[0] if node.children else None
        prefix = text(start).lower() if start is not None and start.type == 'string_start' else ''
        raw, fstr = 'r' in prefix, 'f' in prefix
        out, hints = [], set()
        for c in node.children:
            if c.type == 'string_content':
                content = text(c) if raw else _unescape(text(c))
                out.append(content.replace('{{', '{').replace('}}', '}') if fstr else content)
            elif c.type == 'escape_interpolation':
                out.append(text(c)[:1])
            elif c.type == 'interpolation':
                expr = c.named_children[0] if c.named_children else None
                out.append(self._interpolation(ctx, expr, depth, hints))
        return _V(''.join(out), frozenset(hints), LIT)

    def _interpolation(self, ctx, expr, depth, hints):
        if expr is None:
            return '{param}'
        hints.add(text(expr)[:200])
        if expr.type == 'identifier':
            vs = self._identifier(ctx, expr, depth + 1, interpolated=True)
        else:
            vs = self._values(ctx, expr, depth + 1)
        if len(vs) == 1 and vs[0].kind in (LIT, PARAM):
            hints.update(vs[0].hints)
            return vs[0].text
        for v in vs:
            hints.update(v.hints)
        return '{' + placeholder(text(expr)) + '}'

    def _identifier(self, ctx, node, depth, interpolated=False):
        name = text(node)
        f, func, cls = ctx
        if func is not None:
            assigns = self._locals(f, func).get(name, [])
            prior = [a for a in assigns if a[0] <= node.start_byte]
            if prior:
                if interpolated and len(assigns) > 1:
                    return [_V('{' + name + '}', frozenset({name}), UNK)]
                return self._assigned(ctx, prior, depth)
            if name in {p for p, _ in _params(func)}:
                return [_V(_mark(name), frozenset(), PARAM)]
        found = self._lookup(f, name, before=node.start_byte if func is None else None)
        if found and found[0] == 'value':
            return self._values((found[1], None, None), found[2], depth + 1)
        return [self._unk(node)]

    def _assigned(self, ctx, prior, depth):
        k = max((i for i, a in enumerate(prior) if not a[2]), default=0)
        vs = self._values(ctx, prior[k][1], depth + 1)
        for _, value, aug in prior[k + 1 :]:
            if aug:
                vs = self._join(vs, self._values(ctx, value, depth + 1))
        return vs

    def _attribute(self, ctx, node, depth):
        f, func, cls = ctx
        obj = node.child_by_field_name('object')
        attr = text(node.child_by_field_name('attribute'))
        if obj.type == 'identifier' and text(obj) in ('self', 'cls'):
            value = self._class_attrs(f, cls)[0].get(attr) if cls is not None else None
            return self._values((f, None, cls), value, depth + 1) if value is not None else [self._unk(node)]
        found = self._lookup_expr(f, node)
        if found and found[0] == 'value':
            return self._values((found[1], None, None), found[2], depth + 1)
        return [self._unk(node)]

    def _class_attrs(self, f, cls):
        """({name: value} of class-level assignments, {attr: value} of the first `self.attr = ...`), per class."""
        key = (f.path, cls.start_byte)
        found = self._attrs_cache.get(key)
        if found is None:
            own, inst = {}, {}
            body = cls.child_by_field_name('body')
            for st in body.named_children if body is not None else ():
                if st.type == 'expression_statement':
                    for a in st.named_children:
                        if a.type == 'assignment':
                            for n, v in _targets(a.child_by_field_name('left'), a.child_by_field_name('right')):
                                own.setdefault(n, v)
            for n in walk(body, ('assignment',)) if body is not None else ():
                left = n.child_by_field_name('left')
                if left.type == 'attribute' and text(left.child_by_field_name('object')) in ('self', 'cls'):
                    inst.setdefault(text(left.child_by_field_name('attribute')), n.child_by_field_name('right'))
            found = self._attrs_cache[key] = (own, inst)
        return found

    @staticmethod
    def _join(left, right):
        out = []
        for a, b in itertools.product(left, right):
            kind = UNK if a.kind == UNK and b.kind == UNK else LIT
            out.append(_V(a.text + b.text, a.hints | b.hints, kind))
        return out[:MAX_ALTS]

    def _concat(self, ctx, node, depth):
        ops, n = [], node
        while n.type == 'binary_operator' and n.child_by_field_name('operator').type == '+':
            ops.append(n.child_by_field_name('right'))
            n = n.child_by_field_name('left')
        ops.append(n)
        ops.reverse()
        acc = self._values(ctx, ops[0], depth + 1)
        if all(v.kind == UNK for v in acc):  # an unknown first operand is the base URL
            hints = frozenset().union(*(v.hints for v in acc)) | {text(ops[0])[:200]}
            acc = [_V('{}', hints, UNK)]
        for op in ops[1:]:
            acc = self._join(acc, self._values(ctx, op, depth + 1))
        acc = [v for v in acc if _base_ok(v, text(ops[0]))]  # name + '_state' is a key, not a URL
        if all(v.kind == UNK for v in acc):  # no string in sight: arithmetic, not a URL
            return [self._unk(node)]
        return acc

    def _percent(self, ctx, node, depth):
        right = node.child_by_field_name('right')
        out = []
        for v in self._values(ctx, node.child_by_field_name('left'), depth + 1):
            if v.kind != LIT:
                continue
            s = '{}' + v.text[2:] if v.text.startswith('%s') else v.text
            s = re.sub(r'%\((\w+)\)[sdifr]', r'{\1}', s)
            s = re.sub(r'%[sdifr]', '{param}', s).replace('%%', '%')
            out.append(_V(s, v.hints | {text(right)[:200]}, LIT))
        return out

    def _call_value(self, ctx, node, depth):
        fn = node.child_by_field_name('function')
        pos, kw = _args(node.child_by_field_name('arguments'))
        if fn.type == 'attribute':
            attr = text(fn.child_by_field_name('attribute'))
            obj = fn.child_by_field_name('object')
            if attr == 'format':
                return self._format(ctx, obj, pos, kw, depth)
            if attr == 'join' and obj.type == 'string' and pos and pos[0].type in ('list', 'tuple'):
                sep = self._string(ctx, obj, depth).text
                acc = [_V('', frozenset(), LIT)]
                for i, item in enumerate(pos[0].named_children):
                    part = self._values(ctx, item, depth + 1)
                    acc = self._join(acc, part if i == 0 else self._join([_V(sep)], part))
                return acc
            if attr in _JOINS or (attr == 'join' and text(obj) in _PATH_JOINS):
                return self._urljoin(ctx, node, pos, depth)
            if attr in ('rstrip', 'lstrip', 'strip'):
                return self._values(ctx, obj, depth + 1)
        elif fn.type == 'identifier':
            name = text(fn)
            if name in _JOINS:
                return self._urljoin(ctx, node, pos, depth)
            if name in ('str', 'cast') and pos:
                return self._values(ctx, pos[-1], depth + 1)
        return None

    def _urljoin(self, ctx, node, pos, depth):
        if not pos:
            return None
        acc = self._values(ctx, pos[0], depth + 1)
        if all(v.kind == UNK for v in acc):
            acc = [_V('{}', frozenset().union(*(v.hints for v in acc)) | {text(pos[0])[:200]}, LIT)]
        for p in pos[1:]:
            acc = self._join(self._join(acc, [_V('/')]), self._values(ctx, p, depth + 1))
        return acc

    def _format(self, ctx, obj, pos, kw, depth):
        out = []
        for v in self._values(ctx, obj, depth + 1):
            if v.kind != LIT:
                continue
            hints, counter, base = set(v.hints), [0], []

            def replace(m, hints=hints, counter=counter, base=base):
                field = re.split(r'[!:]', m.group(1))[0]
                key = None
                if field == '':
                    idx = counter[0]
                    counter[0] += 1
                    arg = pos[idx] if idx < len(pos) else None
                elif field.isdigit():
                    arg = pos[int(field)] if int(field) < len(pos) else None
                else:
                    key = re.split(r'[.\[]', field)[0]
                    arg = kw.get(key)
                if arg is None:
                    return '{' + (key or 'param') + '}'
                a = self._values(ctx, arg, depth + 1)[0]
                hints.update(a.hints)
                if a.kind in (LIT, PARAM):
                    return a.text
                hints.add(text(arg)[:200])
                if m.start() == 0:
                    base.append(text(arg))
                    return '{}'
                return '{' + (key or placeholder(text(arg))) + '}'

            formatted = _V(re.sub(r'\{([^{}]*)\}', replace, v.text), frozenset(hints), LIT)
            if _base_ok(formatted, ''.join(base)):
                out.append(formatted)
        return out

    # --------------------------------------------------------------------------------------------------- requests

    def _method_options(self, ctx, node, depth=0):
        """Methods an expression may give: 'POST', ANY, a parameter marker, or a choice the caller settles.

        A method chosen by a condition over the function's own parameters (`'POST' if data else 'GET'`, or a
        parameter replaced under `if method is None:`) becomes a choice, decided per call site from its arguments.
        """
        func = ctx[1]
        if node.type == 'parenthesized_expression' and node.named_children and depth < 8:
            return self._method_options(ctx, node.named_children[0], depth + 1)
        if func is not None and depth < 8:
            params = {p for p, _ in _params(func)}
            if node.type == 'conditional_expression' and len(node.named_children) == 3:
                then, test, other = node.named_children
                if _test_over(test, params):
                    a, b = self._method_options(ctx, then, depth + 1), self._method_options(ctx, other, depth + 1)
                    if len(a) == 1 and len(b) == 1:
                        return [self._choice(func, test, a[0], b[0])]
            elif node.type == 'identifier' and text(node) in params:
                guarded = self._guarded_method(ctx, node, params, depth)
                if guarded:
                    return guarded
            elif node.type == 'identifier':  # a local: verb = 'PUT' if upload else 'GET'
                prior = [a for a in self._locals(ctx[0], func).get(text(node), []) if a[0] <= node.start_byte]
                if prior:
                    return self._method_options(ctx, prior[-1][1], depth + 1)
        out = []
        for v in self._values(ctx, node):
            if v.kind == LIT and v.text.upper() in HTTP_METHODS:
                out.append(v.text.upper())
            elif v.kind == PARAM:
                out.append(v.text)
            else:
                out.append(ANY)
        return list(dict.fromkeys(out))[:2]

    def _guarded_method(self, ctx, node, params, depth):
        """`if method is None: method = X` before the use: a choice between X and the parameter itself."""
        f, func, _ = ctx
        name = text(node)
        prior = [a for a in self._locals(f, func).get(name, []) if a[0] <= node.start_byte]
        if len(prior) != 1 or prior[0][2]:
            return None
        value = prior[0][1]
        stmt = ancestor(value, ('if_statement', 'function_definition'))
        if stmt is None or stmt.type != 'if_statement':
            return None
        test, body = stmt.child_by_field_name('condition'), stmt.child_by_field_name('consequence')
        inside = body is not None and body.start_byte <= value.start_byte < body.end_byte
        if not inside or not _test_over(test, params) or name not in _identifiers(test):
            return None
        then = self._method_options(ctx, value, depth + 1)
        return [self._choice(func, test, then[0], _mark(name))] if len(then) == 1 else None

    def _choice(self, func, test, then, other):
        self._choices.append((func, test, then, other))
        return f'{_CHOICE}{len(self._choices) - 1}'

    def _decide(self, method, func, bound, defaults):
        """A choice settled by one call site's arguments: the branch it takes, or ANY when that is not known."""
        for _ in range(8):
            if not method.startswith(_CHOICE):
                return method
            owner, test, then, other = self._choices[int(method[1:])]
            truth = _truth(test, bound, defaults) if owner == func else None
            if truth is None:
                return ANY
            method = then if truth else other
        return ANY

    def _is_method_arg(self, ctx, node):
        for v in self._values(ctx, node):
            if v.kind == LIT and v.text.upper() in HTTP_METHODS:
                return True
            if v.kind == PARAM and 'method' in v.text:
                return True
        return False

    def _request(self, f, call, name):
        fn = call.child_by_field_name('function')
        recv = fn.child_by_field_name('object') if fn.type == 'attribute' else None
        pos, kw = _args(call.child_by_field_name('arguments'))
        ctx = self._ctx(f, call)
        method_node, url, methods = None, None, None
        if name == 'urlopen':
            if 'url' in kw:
                url, method_node = kw['url'], kw.get('method', pos[0] if pos else None)
            elif len(pos) >= 2 and self._is_method_arg(ctx, pos[0]):
                method_node, url = pos[0], pos[1]
            else:
                url, method_node = (pos[0] if pos else None), kw.get('method')
            if url is not None and url.type == 'call' and _callee(url) == 'Request':
                rpos, rkw = _args(url.child_by_field_name('arguments'))
                method_node = rkw.get('method', method_node)
                url = rkw.get('url', rpos[0] if rpos else None)
            client = True
        elif recv is None:
            return
        elif name == 'request':
            method_node = kw.get('method', pos[0] if pos else None)
            url = kw.get('url', pos[1] if len(pos) > 1 else None)
            client = _is_client(recv)
        else:
            url = kw.get('url', pos[0] if pos else None)
            methods = [name.upper()]
            client = _is_client(recv)
            if name == 'get' and not client and len(pos) > 1:
                return  # mapping.get(key, default)
        if url is None or url.type in ('list_splat', 'dictionary_splat'):
            return
        if methods is None:
            methods = self._method_options(ctx, method_node) if method_node is not None else [ANY]
        hints = self._site_hints(ctx, recv)
        run = _Run(client)
        for v in self._values(ctx, url)[:MAX_ALTS]:
            for m in methods:
                self._settle(ctx, call, v.text, m, hints | v.hints, 0, (0, False, frozenset()), frozenset(), run)

    def _site_hints(self, ctx, recv):
        f, func, cls = ctx
        hints = {f.path}
        if func is not None:
            hints.add(_name(func))
        if cls is not None:
            hints.add(_name(cls))
        if recv is not None:
            hints.add(text(recv)[:200])
            rhs = self._receiver_rhs(ctx, recv)
            if rhs:
                hints.add(rhs[:300])
        return frozenset(h for h in hints if h)

    def _receiver_rhs(self, ctx, recv):
        """The expression a client receiver was created from: `_pool = connection_from_url(settings.SNUBA)`."""
        f, func, cls = ctx
        node = recv
        if node.type == 'attribute':
            obj = node.child_by_field_name('object')
            if obj.type == 'identifier' and text(obj) in ('self', 'cls'):
                value = self._self_attr(f, cls, text(node.child_by_field_name('attribute'))) if cls else None
                return text(value) if value is not None else ''
            found = self._lookup_expr(f, node)
            if found and found[0] == 'value':
                return text(found[2])
            while node.type == 'attribute':
                node = node.child_by_field_name('object')
        if node.type != 'identifier':
            return ''
        name = text(node)
        if func is not None:
            prior = [a for a in self._locals(f, func).get(name, []) if a[0] <= recv.start_byte]
            if prior:
                return text(prior[-1][1])
        found = self._lookup(f, name)
        return text(found[2]) if found and found[0] == 'value' else ''

    def _self_attr(self, f, cls, attr):
        """What `self.attr` was assigned: a class attribute, else the first `self.attr = ...` in the class."""
        own, inst = self._class_attrs(f, cls)
        return own[attr] if attr in own else inst.get(attr)

    def _settle(self, ctx, site, utext, method, hints, depth, prev, stack, run):
        """Emit the request at this call site if it says more than the level below, and forward open parameters."""
        run.settles += 1
        if run.settles > MAX_SETTLES:
            return
        path, base = split_url(_render(utext))
        method_open = bool(_markers(method)) or method.startswith(_CHOICE)
        open_params = _markers(utext) or method_open
        raw = _MARK.sub(lambda m: '{' + m.group(1) + '}', utext)
        lits = PathTemplate.parse(path).literals if path is not None else 0
        ok = path is not None and _pathlike(raw, base, run.client, lits) and bool(PathTemplate.parse(path).segments)
        lits = lits if ok else 0
        shown = ANY if method_open else method
        if ok:
            if depth == 0:
                emit = lits >= 1 or not open_params
            else:
                emit = lits > prev[0] or (lits >= 1 and (prev[1] and not method_open or not set(base) <= prev[2]))
            if emit:
                self._emit(ctx, site, path, shown, hints | set(base))
        if open_params and ctx[1] is not None and depth < MAX_FORWARD and (ok or run.client):
            here = (max(lits, prev[0]), method_open, prev[2] | set(base))
            self._forward(ctx, utext, method, hints, depth, here, stack, run)

    def _emit(self, ctx, site, path, method, hints, kind='request', route_name=''):
        f = ctx[0]
        tmpl = PathTemplate.parse(path) if path is not None else None
        key = (f.path, line(site), str(tmpl), method, kind, route_name)
        old = self.calls.get(key)
        hints = frozenset(h for h in hints if h and '\x00' not in h)
        if old is not None:
            hints = hints | old.hints
        self.calls[key] = Call(
            repo=self.repo,
            file=f.path,
            line=line(site),
            path=tmpl,
            method=method,
            function=self._qualified(ctx),
            hints=hints,
            kind=kind,
            route_name=route_name,
            test=self._in_test(f, site),
        )

    # ------------------------------------------------------------------------------------------------- forwarding

    def _file_calls(self, f):
        if f.calls is None:
            f.calls = {}
            for c in ts.QueryCursor(ts.Query(self._lang, _CALLS)).captures(f.root).get('call', ()):
                f.calls.setdefault(_callee(c), []).append(c)
        return f.calls

    def _mentioning(self, name):
        """Files whose source calls `name(` somewhere, from an index built on first use."""
        if self._mentions is None:
            self._mentions = {}
            for f in self.files.values():
                for n in set(_CALL_NAME.findall(f.src)):
                    self._mentions.setdefault(n.decode(), []).append(f)
        return self._mentions.get(name, [])

    def _unique_def(self, name):
        defs = self.defs.get(name, [])
        return len([d for d in defs if not d[0].test]) == 1

    def _callers(self, f, func):
        name = _name(func)
        sites = [(f, c) for c in self._file_calls(f).get(name, ())]
        if name not in _STOP and self._unique_def(name):
            for g in self._mentioning(name):
                if g is not f:
                    sites += [(g, c) for c in self._file_calls(g).get(name, ())]
        return [(g, c) for g, c in sites if ancestor(c, ('function_definition',)) != func][:MAX_SITES]

    def _forward(self, ctx, utext, method, hints, depth, prev, stack, run):
        f, func, cls = ctx
        key = (f.path, func.start_byte)
        if key in stack or (key, utext, method, prev) in run.seen:
            return  # a cycle, or this function was already forwarded with the same open values
        run.seen.add((key, utext, method, prev))
        params = _params(func)
        if _is_method(func) and params and params[0][0] in ('self', 'cls'):
            params = params[1:]
        defaults = dict(params)
        for g, call in self._callers(f, func):
            ctx2 = self._ctx(g, call)
            pos, kw = _args(call.child_by_field_name('arguments'))
            if any(a.type == 'list_splat' for a in pos):
                continue  # positions unknown
            bound = {params[i][0]: a for i, a in enumerate(pos[: len(params)]) if a.type != 'dictionary_splat'}
            bound.update(kw)
            decided = self._decide(method, func, bound, defaults)
            in_url = _markers(utext)
            needed = sorted(in_url | _markers(decided))
            options = []
            for name in needed:
                if name in bound:
                    node, scope = bound[name], ctx2
                elif defaults.get(name) is not None:
                    node, scope = defaults[name], (f, None, cls)
                else:
                    options.append([_V('{' + name + '}', frozenset(), UNK)])
                    continue
                if name in in_url:
                    options.append(self._values(scope, node))
                else:
                    options.append([_V(m) for m in self._method_options(scope, node)])
            fn = call.child_by_field_name('function')
            recv = fn.child_by_field_name('object') if fn.type == 'attribute' else None
            site = self._site_hints(ctx2, recv) | {text(fn)[:200]}
            for combo in itertools.islice(itertools.product(*options), MAX_ALTS):
                t2, m2, h2 = utext, decided, set(hints) | site
                for name, v in zip(needed, combo, strict=True):
                    t2 = t2.replace(_mark(name), v.text)
                    m2 = m2.replace(_mark(name), v.text)
                    h2 |= v.hints
                if not _markers(m2) and not m2.startswith(_CHOICE):
                    m2 = m2.upper() if m2.upper() in HTTP_METHODS else ANY
                self._settle(ctx2, call, t2, m2, frozenset(h2), depth + 1, prev, stack | {key}, run)

    # --------------------------------------------------------------------------------------------------- payloads

    def _payload(self, f, call):
        fn = call.child_by_field_name('function')
        if fn.type == 'attribute' and not text(fn.child_by_field_name('object')).endswith(('urls', 'urlresolvers')):
            return
        pos, kw = _args(call.child_by_field_name('arguments'))
        node = kw.get('viewname', pos[0] if pos else None)
        if node is None or node.type not in ('string', 'concatenated_string', 'identifier', 'attribute'):
            return
        ctx = self._ctx(f, call)
        v = self._values(ctx, node)[0]
        if v.kind != LIT or not v.text or re.search(r'[\s{}\x00]', v.text):
            return
        hints = {f.path, self._qualified(ctx)}
        if not self._in_test(f, call):
            hints |= self._payload_hints(f, ctx)
        self._emit(ctx, call, None, ANY, hints, kind='payload', route_name=v.text)

    def _payload_hints(self, f, ctx):
        """Words that may name the service a reverse() URL is handed to.

        The module docstring, the identifiers and strings of the enclosing function (not its docstring, which
        talks about other code), and the qualified names and files of the production functions that call it, two
        levels up. The callers' own local words are left out: they name services by accident (SAML's RelayState).
        """
        hints = set()
        doc = _docstring(f.root)
        if doc is not None:
            hints.add(text(doc))
        func = ctx[1]
        if func is None:
            return hints
        hints |= self._words(f, func)
        for g, c in self._callers(f, func):
            if self._in_test(g, c):
                continue
            ctx2 = self._ctx(g, c)
            hints |= {g.path, self._qualified(ctx2)}
            if ctx2[1] is None:
                continue
            for h, c2 in self._callers(g, ctx2[1]):
                if not self._in_test(h, c2):
                    hints |= {h.path, self._qualified(self._ctx(h, c2))}
        return hints

    def _words(self, f, func):
        key = (f.path, func.start_byte)
        found = self._words_cache.get(key)
        if found is None:
            doc = _docstring(func.child_by_field_name('body'))
            skip = (doc.start_byte, doc.end_byte) if doc is not None else (0, 0)
            nodes = walk(func, ('identifier', 'string_content'))
            found = frozenset(text(n)[:200] for n in nodes if not skip[0] <= n.start_byte < skip[1])
            self._words_cache[key] = found
        return found

    # ---------------------------------------------------------------------------------------- decorator routes

    def _registration(self, f, call):
        pos, kw = _args(call.child_by_field_name('arguments'))
        target = pos[0] if pos else kw.get('blueprint') or kw.get('router')
        prefix = kw.get('url_prefix') if 'url_prefix' in kw else kw.get('prefix')
        if target is None or prefix is None:
            return
        found = self._lookup_expr(f, target)
        v = self._values(self._ctx(f, call), prefix)[0]
        if found and found[0] == 'value' and v.kind == LIT:
            self.registrations[(found[1].path, found[2].start_byte)] = v.text

    def _prefix(self, f, recv):
        framework = 'fastapi' if b'fastapi' in f.src else 'flask'
        found = self._lookup_expr(f, recv)
        if not found or found[0] != 'value' or found[2].type != 'call':
            return '', framework
        vf, value = found[1], found[2]
        callee = _callee(value)
        if callee in ('APIRouter', 'FastAPI'):
            framework = 'fastapi'
        elif callee in ('Blueprint', 'Flask', 'Quart'):
            framework = 'flask'
        _, kw = _args(value.child_by_field_name('arguments'))
        node = kw.get('url_prefix', kw.get('prefix'))
        own = self._values((vf, None, None), node)[0].text if node is not None else ''
        registered = self.registrations.get((vf.path, value.start_byte))
        if framework == 'fastapi':
            return (registered or '') + own, framework
        return (own if registered is None else registered), framework

    def _decorated(self, f, dec):
        defn = dec.child_by_field_name('definition')
        if defn is None or defn.type != 'function_definition':
            return
        for d in dec.children:
            expr = d.named_children[0] if d.type == 'decorator' and d.named_children else None
            if expr is None or expr.type != 'call':
                continue
            fn = expr.child_by_field_name('function')
            if fn.type != 'attribute':
                continue
            attr = text(fn.child_by_field_name('attribute'))
            if attr not in ('route', 'api_route', 'websocket') and attr not in VERBS:
                continue
            pos, kw = _args(expr.child_by_field_name('arguments'))
            node = pos[0] if pos else kw.get('path', kw.get('rule'))
            verb = [attr.upper()] if attr in VERBS else ['GET']
            self._add_route(f, d, fn.child_by_field_name('object'), node, kw.get('methods'), verb, _name(defn))

    def _url_rule(self, f, call):
        fn = call.child_by_field_name('function')
        pos, kw = _args(call.child_by_field_name('arguments'))
        node = pos[0] if pos else kw.get('rule')
        view = kw.get('view_func', pos[2] if len(pos) > 2 else None)
        handler = text(view) if view is not None else ''
        self._add_route(f, call, fn.child_by_field_name('object'), node, kw.get('methods'), ['GET'], handler)

    def _add_route(self, f, site, recv, node, methods_node, default, handler):
        if node is None:
            return
        v = self._values(self._ctx(f, site), node)[0]
        raw = v.text
        if v.kind != LIT or re.search(r'\s|\x00', raw) or not (raw == '' or raw.startswith('/') or '<' in raw):
            return
        methods = self._route_methods(f, site, methods_node) if methods_node is not None else default
        prefix, framework = self._prefix(f, recv)
        if not raw and not prefix:
            return  # '' names a router's own prefix; without one it is more likely some other decorator
        path = PathTemplate.parse(_flask_path(prefix + raw))
        self.routes.append(Route(self.repo, f.path, line(site), path, frozenset(methods), handler, '', framework))

    def _route_methods(self, f, site, node):
        """methods=[...] (a literal list or a module-level name for one); ANY when any entry is unknown."""
        if node.type in ('identifier', 'attribute'):
            found = self._lookup_expr(f, node)
            node = found[2] if found and found[0] == 'value' else node
            f = found[1] if found and found[0] == 'value' else f
            site = node
        if node.type not in ('list', 'tuple', 'set'):
            return [ANY]
        out = []
        for m in node.named_children:
            v = self._values(self._ctx(f, site), m)[0]
            if v.kind != LIT or v.text.upper() not in HTTP_METHODS:
                return [ANY]
            out.append(v.text.upper())
        return out or [ANY]

    # ----------------------------------------------------------------------------------------------------- django

    def _django(self):
        roots = []
        for f in self.files.values():
            if b'ROOT_URLCONF' in f.src:
                found = self._lookup(f, 'ROOT_URLCONF')
                value = found[2] if found and found[0] == 'value' and found[1] is f else None
                if value is not None and value.type == 'string':
                    mf = self._modfile(('abs', self._string((f, None, None), value, 0).text))
                    if mf is not None:
                        roots.append((f.test, mf))
        if roots:
            best = min(t for t, _ in roots)
            for mf in dict.fromkeys(mf for t, mf in roots if t == best):
                self._compose_list(mf, 'urlpatterns', [''], frozenset(), self.routes, set())
            return
        candidates = [f for f in self.files.values() if b'urlpatterns' in f.src and 'urlpatterns' in self._lists(f)]
        included, found = set(), {}
        for f in candidates:
            found[f.path], reached = [], set()
            self._compose_list(f, 'urlpatterns', [''], frozenset(), found[f.path], reached)
            included |= reached - {f.path}
        for path, routes in found.items():
            if path not in included:
                self.routes += routes

    def _lists(self, f):
        """Module-level URL lists: name -> [('expr', node) | ('item', node)] from assignments, += and append/extend."""
        if f.lists is not None:
            return f.lists
        out = {}
        for st in _module_statements(f.root):
            if st.type != 'expression_statement':
                continue
            for e in st.named_children:
                if e.type == 'assignment':
                    left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
                    if left.type == 'identifier' and right is not None:
                        name = text(left)
                        if name in _identifiers(right):  # urlpatterns = urlpatterns + [...]: keeps what it had
                            out.setdefault(name, []).append(('expr', right))
                        else:
                            out[name] = [('expr', right)]
                elif e.type == 'augmented_assignment' and text(e.child_by_field_name('operator')) == '+=':
                    left = e.child_by_field_name('left')
                    if left.type == 'identifier':
                        out.setdefault(text(left), []).append(('expr', e.child_by_field_name('right')))
                elif e.type == 'call':
                    fn = e.child_by_field_name('function')
                    if fn.type != 'attribute' or fn.child_by_field_name('object').type != 'identifier':
                        continue
                    pos, _ = _args(e.child_by_field_name('arguments'))
                    owner, attr = text(fn.child_by_field_name('object')), text(fn.child_by_field_name('attribute'))
                    if attr == 'append' and pos:
                        out.setdefault(owner, []).append(('item', pos[0]))
                    elif attr == 'extend' and pos:
                        out.setdefault(owner, []).append(('expr', pos[0]))
                    elif attr == 'insert' and len(pos) > 1:
                        out.setdefault(owner, []).append(('item', pos[1]))
        f.lists = out
        return out

    def _list_ref(self, f, name, depth=0):
        if name in self._lists(f):
            return f, name
        imp = self._module(f)[3].get(name)
        if imp is not None and imp[1] is not None and depth < MAX_IMPORTS:
            mf = self._modfile(imp[0])
            if mf is not None:
                return self._list_ref(mf, imp[1], depth + 1)
        return None

    def _list_entries(self, f, name, seen, depth):
        key = (f.path, name)
        if key in seen:
            return
        for _, node in self._lists(f).get(name, ()):
            yield from self._entries(f, node, None, seen | {key}, depth + 1)

    def _entries(self, f, node, binds, seen, depth=0):
        """The path()/re_path()/url() calls a URL list expression contains: [(file, call, binds)]."""
        if node is None or depth > 30:
            return
        t = node.type
        if t in ('list', 'tuple', 'expression_list', 'set', 'list_splat', 'parenthesized_expression'):
            for c in node.named_children:
                yield from self._entries(f, c, binds, seen, depth + 1)
        elif t == 'binary_operator':
            yield from self._entries(f, node.child_by_field_name('left'), binds, seen, depth + 1)
            yield from self._entries(f, node.child_by_field_name('right'), binds, seen, depth + 1)
        elif t == 'call':
            yield from self._call_entries(f, node, binds, seen, depth)
        elif t == 'identifier':
            name = text(node)
            if binds is not None:
                local = self._locals(f, binds[0]).get(name)
                if local:
                    yield from self._entries(f, local[-1][1], binds, seen, depth + 1)
                    return
            ref = self._list_ref(f, name)
            if ref is not None:
                yield from self._list_entries(ref[0], ref[1], seen, depth)
        elif t == 'attribute':
            found = self._lookup_expr(f, node.child_by_field_name('object'))
            mf = self._modfile(found[1]) if found and found[0] == 'module' else None
            ref = self._list_ref(mf, text(node.child_by_field_name('attribute'))) if mf is not None else None
            if ref is not None:
                yield from self._list_entries(ref[0], ref[1], seen, depth)

    def _call_entries(self, f, node, binds, seen, depth):
        name = _callee(node)
        pos, kw = _args(node.child_by_field_name('arguments'))
        if name in ('path', 're_path', 'url') and (len(pos) >= 2 or 'view' in kw):
            yield (f, node, binds)
        elif name == 'patterns':
            for a in pos[1:]:
                yield from self._entries(f, a, binds, seen, depth + 1)
        elif name in ('list', 'tuple') and pos:
            yield from self._entries(f, pos[0], binds, seen, depth + 1)
        else:  # a function that builds the list: include(create_group_urls('prefix'))
            found = self._lookup_expr(f, node.child_by_field_name('function'))
            if not found or found[0] != 'def' or (found[1].path, found[2].start_byte) in seen:
                return
            df, func = found[1], found[2]
            params = _params(func)
            values = {}
            for i, a in enumerate(pos[: len(params)]):
                values[params[i][0]] = a
            values.update(kw)
            bound = {}
            for k, a in values.items():
                v = self._values(self._ctx(f, node), a)[0]
                if v.kind == LIT and not _markers(v.text):
                    bound[k] = v.text
            for r in _body_nodes(func.child_by_field_name('body')):
                if r.type == 'return_statement' and r.named_children:
                    key = (df.path, func.start_byte)
                    yield from self._entries(df, r.named_children[0], (func, bound), seen | {key}, depth + 1)

    def _compose_list(self, f, name, prefixes, stack, out, included):
        ref = self._list_ref(f, name)
        if ref is not None:
            for pf, pat, binds in self._list_entries(ref[0], ref[1], frozenset(), 0):
                self._compose_entry(pf, pat, binds, prefixes, stack, out, included, False)

    def _compose_entry(self, f, pat, binds, prefixes, stack, out, included, nested):
        key = (f.path, pat.start_byte)
        if key in stack:
            return
        if nested:
            included.add(f.path)
        pos, kw = _args(pat.child_by_field_name('arguments'))
        node = pos[0] if pos else kw.get('route', kw.get('regex'))
        view = pos[1] if len(pos) > 1 else kw.get('view')
        v = self._values(self._ctx(f, pat), node)[0] if node is not None else None
        if v is None or v.kind != LIT or _markers(v.text):
            alts = ['{param}']
        elif _callee(pat) == 'path':
            alts = [_flask_path(v.text)]
        else:
            alts = _regex_templates(v.text)
        full = [p + a for p in prefixes for a in alts][:MAX_ROUTE_ALTS]
        if view is None:
            return
        if view.type == 'call' and _callee(view) == 'include':
            ipos, ikw = _args(view.child_by_field_name('arguments'))
            arg = ipos[0] if ipos else ikw.get('arg')
            if arg is not None and arg.type == 'tuple' and arg.named_children:
                arg = arg.named_children[0]
            if arg is None:
                return
            if arg.type == 'string':
                mf = self._modfile(('abs', self._string(self._ctx(f, pat), arg, 0).text))
                ref = self._list_ref(mf, 'urlpatterns') if mf is not None else None
                entries = self._list_entries(ref[0], ref[1], frozenset(), 0) if ref else ()
            else:
                entries = self._entries(f, arg, binds, frozenset())
            for pf, child, cbinds in entries:
                self._compose_entry(pf, child, cbinds, full, stack | {key}, out, included, True)
            return
        handler, methods = self._view(f, view)
        name = self._route_name(f, kw.get('name'), binds)
        for p in full:
            out.append(
                Route(self.repo, f.path, line(pat), PathTemplate.parse('/' + p), methods, handler, name, 'django')
            )

    def _route_name(self, f, node, binds):
        if node is None:
            return ''
        v = self._values((f, binds[0] if binds else None, None), node)[0]
        if v.kind == PARAM:
            v = _V(v.text)
        name = _MARK.sub(lambda m: (binds[1] if binds else {}).get(m.group(1), '\x00'), v.text)
        return name if v.kind == LIT and '\x00' not in name and '{' not in name else ''

    def _view(self, f, view):
        if view.type == 'call':
            fn = view.child_by_field_name('function')
            if fn.type == 'attribute' and text(fn.child_by_field_name('attribute')) == 'as_view':
                cls_expr = fn.child_by_field_name('object')
                return text(cls_expr), self._class_methods(f, cls_expr)
            pos, _ = _args(view.child_by_field_name('arguments'))
            if pos and pos[0].type == 'call':  # a decorated view: csrf_exempt(View.as_view())
                return self._view(f, pos[0])
        return text(view), frozenset({ANY})

    def _find_class(self, f, expr):
        found = self._lookup_expr(f, expr)
        if found and found[0] == 'class':
            return found[1], found[2]
        name = text(expr).split('.')[-1]
        cands = self.classes.get(name, [])
        prod = [c for c in cands if not c[0].test] or cands
        return prod[0] if prod else (None, None)

    def _class_methods(self, f, expr):
        cf, cls = self._find_class(f, expr)
        if cls is None:
            return frozenset({ANY})
        methods = self._own_methods(cls)
        if not methods:
            bases = cls.child_by_field_name('superclasses')
            for b in bases.named_children if bases is not None else ():
                if b.type in ('identifier', 'attribute'):
                    bf, base = self._find_class(cf, b)
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
            if st is not None and st.type == 'function_definition' and _name(st) in VERBS:
                out.add(_name(st).upper())
        return out
