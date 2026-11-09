"""The runtime libraries generated API clients send their requests through, as data."""

from dataclasses import dataclass

from ..syntax.nodes import JsSyntax


@dataclass(frozen=True)
class GeneratedRuntime:
    """A runtime library of generated clients.

    libraries: the modules it is imported from; factory: the function that makes a runtime from the client's
    defaults (`Oazapfts.runtime(defaults)`); base: the property of those defaults that holds the base URL; senders:
    the runtime's methods that send a request, given the URL first and the request options second; wrappers: its
    methods that wrap request options (`oazapfts.json({ ...opts, method: 'PUT', body })`); queries: the modules whose
    helpers build a query string (`QS.query(...)`), which is not part of the path.
    """

    libraries: tuple[str, ...]
    factory: str
    base: str
    senders: frozenset
    wrappers: frozenset
    queries: tuple[str, ...]


class GeneratedRuntimes:
    """The table, and what a file imports from it."""

    TABLE = (
        # oazapfts: `export function getPet({ id }, opts) { return oazapfts.ok(oazapfts.fetchJson(`/pets/${id}`, {
        # ...opts })) }` with `const oazapfts = Oazapfts.runtime(defaults)` and `defaults = { baseUrl: '/api' }`.
        # The runtime is '@oazapfts/runtime' (oazapfts 5+) or 'oazapfts/lib/runtime' (oazapfts 4 and before); what
        # `runtime(defaults)` returns sends through fetchText, fetchJson and fetchBlob, and wraps options in json, form
        # and multipart (packages/runtime/src/runtime.ts).
        GeneratedRuntime(
            libraries=('@oazapfts/runtime', 'oazapfts/lib/runtime'),
            factory='runtime',
            base='baseUrl',
            senders=frozenset({'fetchJson', 'fetchText', 'fetchBlob'}),
            wrappers=frozenset({'json', 'form', 'multipart'}),
            queries=('@oazapfts/runtime/query', 'oazapfts/lib/runtime/query'),
        ),
    )
    # bytes a file must contain to import one of the runtimes (checked before parsing)
    MENTIONS = tuple(sorted({lib.split('/')[0].lstrip('@').encode() for r in TABLE for lib in r.libraries}))
    _BY_LIBRARY = {lib: r for r in TABLE for lib in r.libraries}
    _BY_QUERY = {lib: r for r in TABLE for lib in r.queries}

    @classmethod
    def of(cls, library) -> GeneratedRuntime | None:
        return cls._BY_LIBRARY.get(library)

    @classmethod
    def is_query(cls, library) -> bool:
        return library in cls._BY_QUERY


class NamespaceImports:
    """name -> module for `import * as Name from 'module'` (the import table keeps named and default imports)."""

    def __init__(self, source):
        self._names = {}
        for statement in source.root.named_children:
            if statement.type != 'import_statement' or statement.child_by_field_name('source') is None:
                continue
            library = JsSyntax.string(statement.child_by_field_name('source'))
            for clause in (c for c in statement.named_children if c.type == 'import_clause'):
                for space in (c for c in clause.named_children if c.type == 'namespace_import'):
                    name = next((n for n in space.named_children if n.type == 'identifier'), None)
                    if name is not None:
                        self._names[JsSyntax.text(name)] = library

    def get(self, name):
        return self._names.get(name)
