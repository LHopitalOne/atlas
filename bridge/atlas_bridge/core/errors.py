"""Every error the bridge raises. Callers catch BridgeError (or a branch of it); nothing raises a bare Exception.

BridgeError
├── InputError                  something the user gave us is wrong; the message says what to fix
│   ├── NamedInputError         'name=path' arguments
│   ├── AliasError              '--alias word=repo'
│   ├── RepositoryNotFoundError a repository folder that does not exist
│   └── GraphFormatError        a file that is not a Graphify graph.json
└── ExtractionError             reading source code failed
    ├── ParserUnavailableError  a tree-sitter grammar is not installed
    └── SourceReadError         a source file cannot be read
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


class ExtractionError(BridgeError):
    pass


class ParserUnavailableError(ExtractionError):
    def __init__(self, language: str):
        super().__init__(f'no tree-sitter grammar for {language}', "install it with pip install 'atlas-bridge[links]'")


class SourceReadError(ExtractionError):
    def __init__(self, path: str, problem: str):
        super().__init__(f'cannot read {path}: {problem}')
