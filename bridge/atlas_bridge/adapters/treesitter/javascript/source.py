"""JsSource: a source file whose syntax tree can be dropped once every collector is done with it."""

from ..kit import SourceFile


class JsSource(SourceFile):
    """The kit's SourceFile keeps its tree for as long as the file lives. A repository's files live until extraction
    ends, so the javascript extractor drops each tree after reading the file (it is parsed again if needed)."""

    @classmethod
    def adopt(cls, source: SourceFile) -> 'JsSource':
        """The same file (bytes shared, not copied), with a tree it can release."""
        return source if isinstance(source, cls) else cls(source.path, source.data, source.grammar, source.test)

    @property
    def parsed(self) -> bool:
        """The tree is held (parsed and not released since)."""
        return self._tree is not None

    def release(self):
        """Drop the parsed tree; the next use of `root` parses the file again."""
        self._tree = None
