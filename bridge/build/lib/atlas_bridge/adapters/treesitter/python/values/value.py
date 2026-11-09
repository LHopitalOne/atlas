"""One possible value of an expression, and the markers that stand for a wrapper function's open parameters."""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, eq=False)
class Value:
    """Text with {placeholders}, parameter markers and a '{}' unknown base; the hints it carries; and its kind.

    LITERAL: built from strings (it may still hold placeholders). PARAM: exactly one parameter of the enclosing
    function, settled at its call sites. UNKNOWN: nothing is known beyond the placeholder.
    """

    LITERAL, PARAM, UNKNOWN = 'lit', 'param', 'unk'
    HINT_LENGTH = 200  # longest expression text kept as a hint

    text: str
    hints: frozenset = frozenset()
    kind: str = LITERAL

    @classmethod
    def hint(cls, text: str) -> str:
        """Expression text as a hint: at most HINT_LENGTH characters."""
        return text[: cls.HINT_LENGTH]

    @property
    def is_literal(self):
        return self.kind == self.LITERAL

    @property
    def is_param(self):
        return self.kind == self.PARAM

    @property
    def is_unknown(self):
        return self.kind == self.UNKNOWN

    @property
    def is_known(self):
        """A literal or a parameter: text the caller can use as it is."""
        return self.kind != self.UNKNOWN


class Marker:
    """How value text encodes what is still open: parameter markers (OPEN name CLOSE), the hole a marker with no
    value leaves (UNRESOLVED), and method choices (CHOICE index). Only this class knows the encoding."""

    OPEN, CLOSE = '\x00', '\x01'  # around a parameter's name
    UNRESOLVED = OPEN  # what fill() leaves for a parameter with no value; every marker starts with it too
    CHOICE = '\x02'  # a method that depends on a condition over the wrapper's parameters: CHOICE + index
    PATTERN = re.compile(f'{OPEN}(\\w+){CLOSE}')  # a parameter marker; group 1 is the parameter's name

    @classmethod
    def wrap(cls, name):
        return f'{cls.OPEN}{name}{cls.CLOSE}'

    @classmethod
    def names(cls, text):
        """The parameter names marked in a text."""
        return set(cls.PATTERN.findall(text))

    @classmethod
    def braces(cls, text):
        """Every marker written as {name}."""
        return cls.PATTERN.sub(lambda m: '{' + m.group(1) + '}', text)

    @classmethod
    def fill(cls, text, values):
        """Markers replaced by values[name]; a marker with no value becomes UNRESOLVED."""
        return cls.PATTERN.sub(lambda m: values.get(m.group(1), cls.UNRESOLVED), text)

    @classmethod
    def is_unresolved(cls, text):
        """Whether a marker or the hole of an unfilled one is still in the text."""
        return cls.UNRESOLVED in text

    @classmethod
    def choice(cls, index: int) -> str:
        """The method text that stands for choice number `index`."""
        return f'{cls.CHOICE}{index}'

    @classmethod
    def choice_index(cls, method: str) -> int:
        """The index a choice's method text stands for."""
        return int(method.removeprefix(cls.CHOICE))

    @classmethod
    def is_choice(cls, method):
        return method.startswith(cls.CHOICE)

    @classmethod
    def is_open(cls, method):
        """A method still waiting for a caller: a parameter marker or a choice."""
        return bool(cls.names(method)) or cls.is_choice(method)
