"""Every error the bridge raises. Callers catch BridgeError (or a branch of it); nothing raises a bare Exception.

BridgeError
├── InputError                  something the user gave us is wrong; the message says what to fix
│   ├── NamedInputError         'name=path' arguments
│   ├── AliasError              '--alias word=repo'
│   ├── RepositoryNotFoundError a repository folder that does not exist
│   ├── GraphFormatError        a file that is not a Graphify graph.json
│   ├── ScipFormatError         a file that is not a SCIP index
│   ├── LinkFormatError         a file that is not the links JSON the links command writes
│   └── LibraryIndexError       a library to follow calls into, with no SCIP indexes to follow them
└── ExtractionError             reading source code failed
    ├── ParserUnavailableError  a tree-sitter grammar is not installed
    ├── SourceReadError         a source file cannot be read
    ├── IndexerUnavailableError a SCIP indexer is not installed
    └── IndexerFailedError      a SCIP indexer ran but did not produce an index
"""


class BridgeError(Exception):
    """Base of every error the bridge raises. `hint` tells the user what to do about it."""

    exit_code = 1

    def __init__(self, message: str, hint: str = ''):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self):
        return f'{self.message} ({self.hint})' if self.hint else self.message


class InputError(BridgeError):
    exit_code = 2


class NamedInputError(InputError):
    def __init__(self, value: str):
        super().__init__(f'cannot read input {value!r}', 'use name=path or a plain path')


class AliasError(InputError):
    def __init__(self, value: str, problem: str = 'use word=repository, e.g. upstream=sentry'):
        super().__init__(f'cannot use alias {value!r}', problem)


class RepositoryNotFoundError(InputError):
    def __init__(self, path: str):
        super().__init__(f'no repository folder at {path!r}')


class GraphFormatError(InputError):
    def __init__(self, source: str, problem: str):
        super().__init__(f'{source} is not a Graphify graph: {problem}', 'pass graphify-out/graph.json')


class ScipFormatError(InputError):
    def __init__(self, source: str, problem: str):
        super().__init__(f'{source} is not a SCIP index: {problem}', 'pass the index.scip an indexer wrote')


class LibraryIndexError(InputError):
    def __init__(self, libraries: list[str]):
        super().__init__(
            f'following calls into {", ".join(libraries)} needs SCIP indexes',
            'index the services and libraries with `index --sandbox`, then pass --scip-dir',
        )


class ExtractionError(BridgeError):
    pass


class ParserUnavailableError(ExtractionError):
    def __init__(self, language: str):
        super().__init__(f'no tree-sitter grammar for {language}', "install it with pip install 'atlas-bridge[links]'")


class SourceReadError(ExtractionError):
    def __init__(self, path: str, problem: str):
        super().__init__(f'cannot read {path}: {problem}')


class IndexerUnavailableError(ExtractionError):
    def __init__(self, tool: str, install: str):
        super().__init__(f'{tool} is not installed', install)


class IndexerFailedError(ExtractionError):
    def __init__(self, tool: str, repo: str, problem: str):
        super().__init__(f'{tool} could not index {repo}: {problem}')


class LinkFormatError(InputError):
    def __init__(self, source: str, problem: str):
        super().__init__(f'{source} is not a links file: {problem}', 'pass the JSON that atlas_bridge links wrote')
