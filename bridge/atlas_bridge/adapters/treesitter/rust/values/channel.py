"""The strings a channel address can hold, followed through fns, struct fields and environment defaults."""

import itertools
import re

from ..blocks import Blocks
from ..names import ItemPath
from ..syntax import RustSyntax
from .fill import FormatFill
from .format import FormatMacro
from .frame import ChannelScope, Frame
from .pieces import UrlPiece
from .resolver import RustValues
from .value import Value


class ChannelValues(RustValues):
    """RustValues followed further, for the address a socket connects to or binds ('127.0.0.1:9000'):

    - a parameter is the argument of each call by path that reaches its fn (`Sender::connect(&addr)`), or of the
      call being followed into the fn;
    - a call by path to a crate fn is what the fn returns, with its parameters bound to the call's arguments;
    - `value.field` is what every struct expression of the value's type stores in the field;
    - `env::var(..).unwrap_or(d)` / `.unwrap_or_else(|_| d)` is the default `d` (the variable is not known);
    - `format!` fills its placeholders with their arguments' values, a `(host, port)` tuple is 'host:port'.

    Each value is a whole string; a part nobody can resolve is '{}'. Cycles (a field set from itself on reconnect)
    end with no value."""

    HANDLERS = {
        **RustValues.HANDLERS,
        'integer_literal': '_integer',
        'tuple_expression': '_tuple',
        'field_expression': '_field',
    }
    MAX_DEPTH = 12  # hops through lets, consts, parameters, fns and fields
    MAX_VALUES = FormatFill.MAX_VALUES
    MAX_STEPS = 2000  # expressions followed for one address
    # (module, fn) of the documented calls that read an environment variable: std::env::var, dotenvy::var.
    ENV_READS = frozenset({('env', 'var'), ('env', 'var_os'), ('dotenv', 'var'), ('dotenvy', 'var')})
    DEFAULTS = frozenset({'unwrap_or', 'unwrap_or_else'})  # Result/Option methods whose argument is the fallback
    PARSE = 'parse'  # `"0.0.0.0:80".parse()`: the same address, as a SocketAddr
    # An integer literal: its base prefix, its digits (with `_` separators) and an optional type suffix ('8_080u16').
    INTEGER = re.compile(r'(?P<base>0[xob])?(?P<digits>[0-9a-fA-F_]+?)(?P<suffix>[ui](?:8|16|32|64|128|size))?')
    BASES = {None: 10, '0x': 16, '0o': 8, '0b': 2}

    def __init__(self, workspace, functions, structs, types):
        super().__init__(workspace)
        self._functions = functions
        self._structs = structs
        self._types = types
        self._active = set()  # keys of the parameters, fields and fns being followed
        self._steps = 0

    def values(self, file, node, join=False) -> list[Value]:
        self._steps = 0
        return self.resolve(node, ChannelScope(file, join))

    def resolve(self, node, scope, depth=0):
        """RustValues.resolve within a budget of MAX_STEPS expressions per address: a parameter fans out to every
        call site, and nested fan-outs multiply."""
        self._steps += 1
        return super().resolve(node, scope, depth) if self._steps <= self.MAX_STEPS else []

    def _integer(self, node, scope, depth):
        """An integer literal in decimal: '8_080u16' -> '8080', '0x1F90' -> '8080'."""
        m = self.INTEGER.fullmatch(RustSyntax.text(node))
        if m is None:
            return []
        try:
            number = int(m.group('digits').replace('_', ''), self.BASES[m.group('base')])
        except ValueError:
            return []
        return [Value(str(number), node, [])]

    def _identifier(self, node, scope, depth):
        return self._named(RustSyntax.text(node), node, scope, depth)

    def _named(self, name, at, scope, depth):
        """A name used at node `at`: a let before it, a parameter of its fn, or a const."""
        value = self._workspace.binding_named(scope.file, name, at)
        if value is not None:
            return self.resolve(value, scope, depth + 1)
        fn = RustSyntax.ancestor(at, ('function_item',))
        if fn is not None and name in self._functions.params(fn)[0]:
            return self._parameter(fn, name, scope, depth)
        hit = self._workspace.const_named(scope.file, name)
        return self.resolve(hit[1], scope.moved(hit[0]), depth + 1) if hit is not None else []

    def _parameter(self, fn, name, scope, depth):
        key = scope.file.key(fn)
        passed = scope.argument(key, name)
        if passed is not None:
            return self.resolve(passed[0], passed[1], depth + 1)
        out = []
        for file, call, arg in self._functions.arguments(scope.file, fn, name):
            out += self._guarded(file.key(call), arg, ChannelScope(file), depth + 1)
        return out

    def _field(self, node, scope, depth):
        owner = self._types.of(scope.file, node.child_by_field_name('value'))
        if owner is None:
            return []
        return self._stored(owner, RustSyntax.text(node.child_by_field_name('field')), depth)

    def _stored(self, owner, field, depth):
        """What the struct expressions of type `owner` store in `field`."""
        out = []
        for file, value in self._structs.initializers(owner.split('::')[-1], field):
            out += self._guarded(file.key(value), value, ChannelScope(file), depth + 1)
        return out

    def _call(self, node, scope, depth):
        target = self._functions.target(scope.file, node) if RustSyntax.method(node) is None else None
        if target is None:
            return super()._call(node, scope, depth)
        return self._inline(node, target, self._functions.params(target[1])[1], scope, depth)

    def _method_call(self, node, fn, args, scope, depth):
        name = RustSyntax.text(fn.child_by_field_name('field'))
        recv = fn.child_by_field_name('value')
        if name in self.DEFAULTS and len(args) == 1 and self._reads_env(scope.file, recv):
            fallback = RustSyntax.unwrap(args[0])
            if fallback is not None and fallback.type == 'closure_expression':
                fallback = fallback.child_by_field_name('body')
            return self.resolve(fallback, scope, depth)
        if name == self.PARSE and not args:
            return self.resolve(recv, scope, depth)
        if name in UrlPiece.CONVERSIONS:
            return super()._method_call(node, fn, args, scope, depth)
        owner = self._types.of(scope.file, recv)
        target = self._functions.method(scope.file, owner.split('::')[-1], name) if owner else None
        if target is None:
            return super()._method_call(node, fn, args, scope, depth)
        return self._inline(node, target, 0, scope, depth)  # `value.f(a)`: `self` is the value, not an argument

    def _inline(self, call, target, skip, scope, depth):
        """What a crate fn returns when called with this call's arguments (after the first `skip`)."""
        file, fn = target
        key = file.key(fn)
        names = self._functions.params(fn)[0]
        args = dict(zip(names, RustSyntax.args(call)[skip:], strict=False))  # a missing argument binds nothing
        inner = ChannelScope(file, frame=Frame(key, args, scope))
        out = []
        for r in Blocks.returns(fn):
            out += self._guarded((key, scope.file.key(call)), r, inner, depth + 1)
        return out

    def _reads_env(self, file, node):
        """Whether a method chain starts from reading an environment variable: `env::var("X").ok()...`."""
        node = RustSyntax.unwrap(node)
        while node is not None and node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                segs = ItemPath.imported(file, fn) if fn is not None and fn.type in RustSyntax.NAMES else []
                return tuple(segs[-2:]) in self.ENV_READS
            node = RustSyntax.unwrap(fn.child_by_field_name('value'))
        return False

    def _tuple(self, node, scope, depth):
        """`(host, port)`, as a socket address is often given: 'host:port'."""
        parts = [c for c in node.named_children if 'comment' not in c.type]
        if len(parts) != 2:
            return []
        hosts = [v.text for v in self.resolve(parts[0], scope, depth)] or [FormatFill.UNKNOWN]
        ports = [v.text for v in self.resolve(parts[1], scope, depth)]
        pairs = itertools.islice(itertools.product(hosts, ports), self.MAX_VALUES)
        return [Value(f'{h}:{p}', node, []) for h, p in pairs]

    def _macro(self, node, scope, depth):
        if RustSyntax.text(node.child_by_field_name('macro')).split('::')[-1] not in self.FORMAT_MACROS:
            return []
        split = FormatMacro.split(node)
        if split is None:
            return []
        fmt, positional, named = split

        def value_of(key):
            if isinstance(key, int):
                tokens = positional[key] if key < len(positional) else []
            elif key in named:
                tokens = named[key]
            else:  # `{host}`: a name in scope where the macro is
                return [v.text for v in self._named(key, node, scope, depth)]
            return [v.text for v in self._tokens(tokens, scope, depth)]

        return [Value(text, node, []) for text in FormatFill.fill(fmt, value_of)]

    def _tokens(self, tokens, scope, depth):
        """A macro argument, which is tokens, not an expression: a name, a literal, or `owner.field`, each maybe
        borrowed (`&x`) or converted (`x.to_string()`)."""
        tokens = [t for t in tokens if t.type != '&']
        while len(tokens) > 3 and self._converts(tokens[-3:]):
            tokens = tokens[:-3]
        if len(tokens) == 1:
            t = tokens[0]
            if t.type == 'identifier':
                return self._named(RustSyntax.text(t), t, scope, depth)
            return self.resolve(t, scope, depth)
        if len(tokens) == 3 and tokens[1].type == '.' and tokens[2].type == 'identifier':
            owner = self._types.of(scope.file, tokens[0])
            return self._stored(owner, RustSyntax.text(tokens[2]), depth) if owner else []
        return []

    @staticmethod
    def _converts(tokens):
        """`.to_string()` as three tokens: a call that changes nothing about the value (UrlPiece.CONVERSIONS)."""
        dot, name, args = tokens
        return dot.type == '.' and RustSyntax.text(name) in UrlPiece.CONVERSIONS and RustSyntax.text(args) == '()'

    def _guarded(self, key, node, scope, depth):
        """resolve(), unless the same parameter, field or fn is already being followed (a cycle)."""
        if key in self._active:
            return []
        self._active.add(key)
        try:
            return self.resolve(node, scope, depth)
        finally:
            self._active.discard(key)
