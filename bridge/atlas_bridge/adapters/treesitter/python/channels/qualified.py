"""Dotted names read through a file's imports: `Producer` after `from confluent_kafka import Producer` is
`confluent_kafka.Producer`, `redis.Redis.from_url` after `import redis` stays itself."""

from ..syntax import PythonSyntax
from ..workspace import AbsoluteModule


class QualifiedNames:
    """The qualified name of a name or dotted expression, as the file's imports spell its first part."""

    def __init__(self, workspace):
        self._workspace = workspace

    def of(self, source, node) -> str:
        """'module.attr.rest' for an imported first name, '' for anything else (a local name, a call, a subscript)."""
        parts = []
        while node is not None and node.type == 'attribute':
            parts.append(PythonSyntax.text(node.child_by_field_name('attribute')))
            node = node.child_by_field_name('object')
        if node is None or node.type != 'identifier':
            return ''
        imp = self._workspace.names.table(source).imported(PythonSyntax.text(node))
        if imp is None or not isinstance(imp.module, AbsoluteModule):
            return ''
        head = imp.module.name if imp.attr is None else f'{imp.module.name}.{imp.attr}'
        return '.'.join([head, *reversed(parts)])

    @staticmethod
    def matches(qualified: str, library: str, dotted: str) -> bool:
        """Whether a qualified name is `dotted` (one or more trailing parts) of the library's top-level module:
        'redis.client.Redis.from_url' matches ('redis', 'Redis.from_url')."""
        if not qualified or qualified.split('.', 1)[0] != library:
            return False
        return qualified == dotted or qualified.endswith('.' + dotted)
