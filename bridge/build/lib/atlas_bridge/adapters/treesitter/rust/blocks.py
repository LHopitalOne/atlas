"""What block-like expressions evaluate to: a block's tail, every match arm, both branches of an if."""

from .syntax import RustSyntax


class Blocks:
    STATEMENTS = frozenset(
        {'expression_statement', 'let_declaration', 'line_comment', 'block_comment', 'attribute_item'}
    )
    BRANCHING = frozenset({'block', 'expression_statement', 'match_expression', 'if_expression'})
    MAX_LEAVES = 64  # branches (match arms, if/else) of one expression

    @classmethod
    def tail(cls, block):
        """The expression a block evaluates to, or None when it ends with a statement."""
        kids = [c for c in block.named_children if 'comment' not in c.type]
        if not kids:
            return None
        last = kids[-1]
        if last.type == 'expression_statement':
            return last if not RustSyntax.text(last).rstrip().endswith(';') else None
        return None if last.type in cls.STATEMENTS or last.type.endswith('_item') else last

    @classmethod
    def branches(cls, node):
        """The expressions a block-like expression evaluates to, one level down."""
        t = node.type
        if t == 'block':
            tail = cls.tail(node)
            return [tail] if tail is not None else []
        if t == 'expression_statement':
            return node.named_children[:1]
        if t == 'match_expression':
            return cls._arms(node)
        if t == 'if_expression':
            return cls._if_branches(node)
        return []

    @classmethod
    def leaves(cls, node):
        """The non-branching expressions a block, match or if/else chain can evaluate to, flattened iteratively."""
        out, stack = [], [node]
        while stack and len(out) < cls.MAX_LEAVES:
            n = RustSyntax.unwrap(stack.pop())
            if n is None:
                continue
            if n.type in cls.BRANCHING:
                stack += reversed(cls.branches(n))
            else:
                out.append(n)
        return out

    @classmethod
    def returns(cls, fn):
        """The expressions a function returns: its tail expression and `return` values."""
        body = fn.child_by_field_name('body')
        out = []
        if body is None:
            return out
        tail = cls.tail(body)
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

    @staticmethod
    def _arms(match):
        body = match.child_by_field_name('body')
        arms = body.named_children if body is not None else []
        return [
            a.child_by_field_name('value') for a in arms if a.type == 'match_arm' and a.child_by_field_name('value')
        ]

    @staticmethod
    def _if_branches(node):
        out = [node.child_by_field_name('consequence')]
        alt = node.child_by_field_name('alternative')
        if alt is not None:
            out += alt.named_children[:1]
        return [b for b in out if b is not None]
