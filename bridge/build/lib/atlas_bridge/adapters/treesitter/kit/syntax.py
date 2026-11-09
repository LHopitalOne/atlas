"""Reading tree-sitter nodes: their text, line, descendants and ancestors."""


class Syntax:
    @staticmethod
    def text(node):
        return node.text.decode('utf-8', 'replace') if node is not None else ''

    @staticmethod
    def line(node):
        return node.start_point[0] + 1

    @staticmethod
    def walk(node, types=None):
        """Every node under `node` (depth first), or only those whose type is in `types`."""
        stack = [node]
        while stack:
            n = stack.pop()
            if types is None or n.type in types:
                yield n
            stack.extend(reversed(n.children))

    @staticmethod
    def ancestor(node, types):
        n = node.parent
        while n is not None and n.type not in types:
            n = n.parent
        return n
