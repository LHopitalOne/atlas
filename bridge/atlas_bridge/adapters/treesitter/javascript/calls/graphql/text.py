"""The text of a GraphQL document as the code writes it: a string, a template literal, a gql-tagged template, or a
name bound to one in this file or another."""

from ...syntax.functions import Functions
from ...syntax.nodes import JsSyntax
from ...syntax.params import Params


class DocumentText:
    """Reads the text of a document expression. Interpolations (`${FRAGMENT}`, usually fragment definitions shared
    between documents) are left out: the root fields of an operation are written in its own text."""

    MAX_DEPTH = 6
    TEXT = frozenset({'string_fragment', 'escape_sequence'})
    NAMES = frozenset({'identifier', 'shorthand_property_identifier', 'member_expression', 'subscript_expression'})

    @classmethod
    def of(cls, module, node, depth=0) -> str | None:
        """The document text of `node` in `module`, or None when it is not written as text the code can read."""
        node = JsSyntax.unwrap(node)
        if node is None or depth > cls.MAX_DEPTH:
            return None
        if node.type in ('string', 'template_string'):
            return ''.join(JsSyntax.text(c) for c in node.children if c.type in cls.TEXT)
        if node.type == 'call_expression':
            tagged = node.child_by_field_name('arguments')  # gql`...`, graphql`...`
            return (
                cls.of(module, tagged, depth + 1) if tagged is not None and tagged.type == 'template_string' else None
            )
        if node.type == 'binary_expression' and JsSyntax.text(node.child_by_field_name('operator')) == '+':
            left = cls.of(module, node.child_by_field_name('left'), depth + 1)
            right = cls.of(module, node.child_by_field_name('right'), depth + 1)
            return left + '\n' + right if left is not None and right is not None else None
        if node.type in cls.NAMES:
            found = module.objects.locate(node)
            if found is None or found.node.id == node.id:
                return None
            return cls.of(found.module, found.node, depth + 1)
        return None

    @staticmethod
    def parameter(module, node):
        """(the named function, the index of its parameter) when `node` is a plain parameter of that function."""
        node = JsSyntax.unwrap(node)
        if node is None or node.type not in ('identifier', 'shorthand_property_identifier'):
            return None
        name = JsSyntax.text(node)
        binding = module.scopes.binding(node, name)
        if binding is None or binding.initializer is not None:
            return None
        fn = binding.node.parent
        if fn is not None and fn.type == 'formal_parameters':
            fn = fn.parent
        if fn is None or fn.type not in Functions.FUNCTIONS or not Functions.name(fn):
            return None
        index = next((p.index for p in Params.of(fn) if p.name == name), None)
        return (fn, index) if index is not None else None
