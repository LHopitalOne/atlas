"""Rust item paths: `crate::a::B<T>::c` read as segments, without generics."""

import re

from .syntax import RustSyntax


class ItemPath:
    GENERIC = re.compile(r'<[^<>]*>')  # an innermost generic argument list: the '<T>' in 'Foo<Option<T>>'
    METHOD = re.compile(r'\bMethod::([A-Z]+)\b')  # an HTTP method named anywhere: `reqwest::Method::POST`
    WORD = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+')  # one word of a CamelCase name: 'Upstream', 'HTTP'

    @classmethod
    def strip_generics(cls, s):
        """'Foo<Option<T>>' -> 'Foo'."""
        while '<' in s:
            stripped = cls.GENERIC.sub('', s)
            if stripped == s:
                break
            s = stripped
        return s

    @classmethod
    def segments(cls, node):
        """'a::b::<T>::c' -> ['a', 'b', 'c']."""
        return [s for s in cls.strip_generics(RustSyntax.text(node)).split('::') if s]

    @classmethod
    def last(cls, node):
        """The type name a path ends with: 'crate::x::Foo<T>' -> 'Foo'."""
        return cls.strip_generics(RustSyntax.text(node)).split('::')[-1]

    @classmethod
    def words(cls, name):
        """'UpstreamQuery' -> 'Upstream Query'; '' for a name of one word."""
        words = cls.WORD.findall(name)
        return ' '.join(words) if len(words) > 1 else ''
