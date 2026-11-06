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

    @classmethod
    def name(cls, symbol: str) -> str:
        if not symbol or symbol.startswith(cls.LOCAL):
            return ''
        for pattern in (cls.PARAMETER, cls.TYPE_PARAMETER, cls.TERMINAL):
            m = pattern.search(symbol)
            if m:
                return cls._unquote(m.group(1))
        return ''

    @staticmethod
    def _unquote(name):
        if len(name) > 1 and name[0] == name[-1] == '`':
            return name[1:-1].replace('``', '`')
        return name
