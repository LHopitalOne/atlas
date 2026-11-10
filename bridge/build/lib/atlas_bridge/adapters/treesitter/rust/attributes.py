"""Attributes that mark test code: #[test], #[tokio::test(..)], #[rstest], #[test_case(..)], #[cfg(test)]."""

from .syntax import RustSyntax


class TestAttributes:
    NAMES = frozenset({'test', 'rstest', 'test_case'})
    SUFFIXES = ('::test', '_test')
    CFG_ALL = 'cfg(all('
    ITEMS = frozenset({'function_item', 'mod_item', 'impl_item'})
    BEFORE_ITEM = frozenset({'attribute_item', 'line_comment', 'block_comment'})

    @classmethod
    def is_test(cls, attr):
        """#[test], #[tokio::test(..)], #[rstest], #[test_case(..)], #[cfg(test)], #[cfg(all(test, ..))]."""
        a = ''.join(attr.split())
        if a.startswith('cfg('):
            if a == 'cfg(test)':
                return True
            if a.startswith(cls.CFG_ALL) and a.endswith('))'):
                return 'test' in cls.top_level_args(a[len(cls.CFG_ALL) : -2])
            return False
        name = a.split('(')[0]
        return name in cls.NAMES or name.endswith(cls.SUFFIXES)

    @staticmethod
    def top_level_args(s):
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

    @classmethod
    def outer(cls, node):
        """Texts of the outer attributes right before an item."""
        out, n = [], node.prev_named_sibling
        while n is not None and n.type in cls.BEFORE_ITEM:
            if n.type == 'attribute_item':
                out += [RustSyntax.text(a) for a in n.named_children if a.type == 'attribute']
            n = n.prev_named_sibling
        return out

    @classmethod
    def encloses(cls, node):
        """Whether `node` is in (or is) a fn, mod or impl marked as a test."""
        n = node
        while n is not None:
            if n.type in cls.ITEMS and any(map(cls.is_test, cls.outer(n))):
                return True
            n = n.parent
        return False
