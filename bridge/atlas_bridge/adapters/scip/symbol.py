"""Names out of SCIP symbol strings: '`sentry.utils.snuba`/_snuba_pool.' is '_snuba_pool'."""

import re


class ScipSymbol:
    """A SCIP symbol is 'scheme manager package version descriptors'. Its name is the last descriptor's: a namespace
    'name/', type 'name#', term 'name.', method 'name(disambiguator).', macro 'name!', parameter '(name)' or type
    parameter '[name]'. Names with unusual characters are backquoted, with '``' for a backquote."""

    LOCAL = 'local '  # local symbols ('local 12') carry no name
    PARAMETER = re.compile(r'\(([^()]+)\)$')  # '...().(path)': a parameter descriptor
    TYPE_PARAMETER = re.compile(r'\[([^\]]+)\]$')  # '...#[T]': a type parameter descriptor
    TERMINAL = re.compile(r'(`(?:[^`]|``)+`|[^\s/#.`()\[\]!:]+)(?:\([^()]*\)\.|[/#.:!])$')  # 'name' + its suffix
    CALLABLE = re.compile(r'\([^()]*\)\.$')  # a method or function descriptor ends in '().'
    METHOD = re.compile(r'#[^#/]+\([^()]*\)\.$')  # 'Class#name().': a method, not a module-level function
    SOURCE_ROOT = re.compile(r'^(`?)(?:src|lib)\.')  # a src/ layout's module path, as its own index writes it
    PARTS = 5  # scheme, manager, package, version, descriptors

    @classmethod
    def name(cls, symbol: str) -> str:
        if not symbol or symbol.startswith(cls.LOCAL):
            return ''
        for pattern in (cls.PARAMETER, cls.TYPE_PARAMETER, cls.TERMINAL):
            m = pattern.search(symbol)
            if m:
                return cls._unquote(m.group(1))
        return ''

    @classmethod
    def is_callable(cls, symbol: str) -> bool:
        return not symbol.startswith(cls.LOCAL) and bool(cls.CALLABLE.search(symbol))

    @classmethod
    def package(cls, symbol: str) -> str:
        """The package a symbol belongs to; the indexers name a repository's own package after the repository."""
        parts = symbol.split(' ', cls.PARTS - 1)
        return parts[2] if len(parts) == cls.PARTS else ''

    @classmethod
    def is_method(cls, symbol: str) -> bool:
        return cls.is_callable(symbol) and cls.METHOD.search(symbol) is not None

    @classmethod
    def key(cls, symbol: str) -> str:
        """The same definition's name in every index: its descriptors alone, since a library's own index and its
        callers' indexes may give its package another name or version, and a src/ layout's module path a 'src.'
        prefix that the installed package does not have."""
        parts = symbol.split(' ', cls.PARTS - 1)
        if len(parts) < cls.PARTS:
            return symbol
        return cls.SOURCE_ROOT.sub(r'\1', parts[-1])

    @staticmethod
    def _unquote(name):
        if len(name) > 1 and name[0] == name[-1] == '`':
            return name[1:-1].replace('``', '`')
        return name
