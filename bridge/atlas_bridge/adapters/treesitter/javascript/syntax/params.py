"""A function's parameters as plain data: which name each position binds, its default, and the properties a
destructured options parameter takes (`{ method = 'GET', body }`)."""

from dataclasses import dataclass

from .nodes import JsSyntax


@dataclass(frozen=True)
class Param:
    """The parameter at `index`: a plain name (with the text of its default), or a destructured object whose
    properties have defaults of their own."""

    index: int
    name: str = ''
    default: str = ''
    props: tuple = ()  # ((property name, default text), ...) of a destructured `{ ... }` parameter

    @property
    def names(self):
        return {self.name} if self.name else {p for p, _ in self.props}


class Params:
    """Reads the parameters of a function, method or arrow function node."""

    DEFAULTED = frozenset({'assignment_pattern', 'object_assignment_pattern'})

    @classmethod
    def of(cls, fn) -> tuple:
        formal = fn.child_by_field_name('parameters')
        single = fn.child_by_field_name('parameter')  # `x => ...`
        nodes = [single] if single is not None else (formal.named_children if formal is not None else [])
        out = []
        for i, node in enumerate(n for n in nodes if n.type != 'comment'):
            param = cls._param(i, node)
            if param is not None:
                out.append(param)
        return tuple(out)

    @classmethod
    def _param(cls, index, node):
        default = node.child_by_field_name('value')  # typescript `p: T = x`
        if node.type in JsSyntax.PARAMETERS:
            node = node.child_by_field_name('pattern')
        elif node.type in cls.DEFAULTED:
            default, node = node.child_by_field_name('right'), node.child_by_field_name('left')
        if node is None:
            return None
        if node.type == 'identifier':
            return Param(index, JsSyntax.text(node), cls._text(default))
        if node.type == 'object_pattern':
            return Param(index, props=tuple(cls._props(node)))
        return None

    @classmethod
    def _props(cls, pattern):
        for p in pattern.named_children:
            if p.type == 'shorthand_property_identifier_pattern':
                yield JsSyntax.text(p), ''
            elif p.type == 'object_assignment_pattern':
                yield JsSyntax.text(p.child_by_field_name('left')), cls._text(p.child_by_field_name('right'))
            elif p.type == 'pair_pattern':
                yield JsSyntax.text(p.child_by_field_name('key')), ''

    @staticmethod
    def _text(node):
        """A default that is a string literal, as its value; '' for anything else."""
        node = JsSyntax.unwrap(node) if node is not None else None
        return JsSyntax.string(node) or '' if node is not None and node.type == 'string' else ''
