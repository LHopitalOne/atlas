"""A `format!` string with its placeholders filled by the values their arguments hold."""

import itertools

from .format import FormatMacro


class FormatFill:
    """Every string a format can produce from a few values per placeholder: "{host}:{}" with host '127.0.0.1' and
    port '41710' -> '127.0.0.1:41710'. A placeholder nobody can resolve stays '{}'."""

    MAX_VALUES = 8  # strings one format may produce
    UNKNOWN = '{}'

    @classmethod
    def fill(cls, fmt, value_of) -> list[str]:
        """value_of(key) -> [str] for a placeholder's argument: an int (positional) or a name ('{host}')."""
        texts, pos, index = [''], 0, 0
        for m in FormatMacro.PLACEHOLDER.finditer(fmt):
            literal = fmt[pos : m.start()]
            pos = m.end()
            if m.group(1) is None:  # '{{' or '}}': one literal brace
                texts = [t + literal + m.group()[0] for t in texts]
                continue
            key = m.group(1).split(':')[0].strip()
            if not key:
                key, index = index, index + 1
            elif key.isascii() and key.isdigit():
                key = int(key)
            values = list(dict.fromkeys(value_of(key))) or [cls.UNKNOWN]
            texts = [t + literal + v for t, v in itertools.islice(itertools.product(texts, values), cls.MAX_VALUES)]
        return [t + fmt[pos:] for t in texts]
