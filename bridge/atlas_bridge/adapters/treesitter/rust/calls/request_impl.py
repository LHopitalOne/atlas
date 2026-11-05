"""A type implementing a request trait: its names, path functions and the method each path is sent with."""

import re

from .....core.http import ANY
from ..names import ItemPath
from ..syntax import RustSyntax


class RequestImpl:
    """`impl UpstreamRequest for SendEnvelope { fn method(..); fn path(..) }`."""

    PATH_FNS = ('endpoint', 'path', 'url')  # fns whose return value is the request path, in a fixed order
    METHOD = ItemPath.METHOD
    ARM_PATH = re.compile(r'[\w:]+')  # the path a match arm's pattern starts with: 'Kind::Create' of 'Kind::Create{..}'

    def __init__(self, trait, type_node, body):
        segs = ItemPath.segments(trait)
        self._trait_name = segs[-1] if segs else RustSyntax.text(trait)
        self._type_name = ItemPath.last(type_node)
        self._fns = {RustSyntax.name(n): n for n in body.named_children if n.type == 'function_item'}
        self._method, self._arm_methods = ANY, {}
        if 'method' in self._fns:
            self._read_method(self._fns['method'].child_by_field_name('body'))

    @classmethod
    def of(cls, impl) -> 'RequestImpl | None':
        """The request impl an `impl_item` is, or None when it implements no trait (or has no body)."""
        trait = impl.child_by_field_name('trait')
        body = impl.child_by_field_name('body')
        if trait is None or body is None:
            return None
        return cls(trait, impl.child_by_field_name('type'), body)

    @property
    def trait_name(self) -> str:
        return self._trait_name

    @property
    def type_name(self) -> str:
        return self._type_name

    def path_fns(self):
        """[(name, fn node)] of the fns that return the request path."""
        return [(name, self._fns[name]) for name in self.PATH_FNS if name in self._fns]

    def hints(self):
        """The trait and type names, also split into words: 'UpstreamQuery' -> 'Upstream Query'."""
        names = (self.trait_name, self.type_name)
        return {*names} | {h for h in map(ItemPath.words, names) if h}

    def method_of(self, node):
        """The method a path value is sent with: of the matching arm when `fn method` matches on the same kind."""
        arm = RustSyntax.ancestor(node, ('match_arm', 'function_item'))
        arm_key = self.arm_key(arm) if arm is not None and arm.type == 'match_arm' else None
        return self._arm_methods.get(arm_key, self._method)

    @classmethod
    def arm_key(cls, arm):
        """A match arm's pattern, as the path it names: `Kind::Create { .. }` -> 'Kind::Create'."""
        pattern = ''.join(RustSyntax.text(arm.child_by_field_name('pattern')).split())
        m = cls.ARM_PATH.match(pattern)
        return m.group() if m else pattern

    def _read_method(self, body):
        found = set(self.METHOD.findall(RustSyntax.text(body)))
        self._method = found.pop() if len(found) == 1 else ANY
        for arm in RustSyntax.walk(body, ('match_arm',)) if body is not None else ():
            found = set(self.METHOD.findall(RustSyntax.text(arm.child_by_field_name('value'))))
            if len(found) == 1:
                self._arm_methods[self.arm_key(arm)] = found.pop()
