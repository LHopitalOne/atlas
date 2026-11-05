"""HTTP verbs as Python clients and frameworks name them."""


class HttpVerbs:
    """The lowercase verb names of client methods and route decorators, and the HTTP methods they stand for."""

    NAMES = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
    METHODS = frozenset(v.upper() for v in NAMES)

    @classmethod
    def method(cls, text: str):
        """'post' -> 'POST'; None when the text is not an HTTP method."""
        upper = text.upper()
        return upper if upper in cls.METHODS else None
