"""Splitting identifiers and hint text into lower-case words: 'SymbolicatorSession', 'snuba_pool', 'SENTRY_SNUBA'."""

import re


class Words:
    """Lower-case words in code text. camelCase and snake_case boundaries, dots and slashes all split words."""

    CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')  # between 'symbolicator' and 'Session'
    SEPARATOR = re.compile(r'[^a-z0-9]+')  # anything that is not a lower-case letter or digit, after lower-casing

    @classmethod
    def of(cls, text: str) -> set[str]:
        return set(cls.ordered(text))

    @classmethod
    def ordered(cls, text: str) -> list[str]:
        spaced = cls.CAMEL_BOUNDARY.sub(' ', text)
        return [w for w in cls.SEPARATOR.split(spaced.lower()) if w]
