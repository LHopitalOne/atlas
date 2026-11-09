"""Writes small SCIP indexes for tests: the protobuf wire format by hand, the way indexers lay it out."""


class ScipBuilder:
    """documents: {path: [(line (1-based), symbol, roles)]}. typed=True writes SingleLineRange (field 8) instead of
    the deprecated packed range (field 1)."""

    def __init__(self, typed=False):
        self._typed = typed
        self._docs = {}

    def occurrence(self, path, line, symbol, definition=False, span=None):
        """span: (first, last) line of a definition's body, written as its enclosing range."""
        self._docs.setdefault(path, []).append((line, symbol, 1 if definition else 8, span))
        return self

    def build(self) -> bytes:
        return b''.join(self._len(2, self._document(p, occs)) for p, occs in self._docs.items())

    def _document(self, path, occs):
        return self._len(1, path.encode()) + b''.join(self._len(2, self._occurrence(*o)) for o in occs)

    def _occurrence(self, line, symbol, roles, span=None):
        zero_based = line - 1
        if self._typed:
            line_field = self._varint_field(1, zero_based) if zero_based else b''  # proto3 omits zeros
            rng = self._len(8, line_field + self._varint_field(2, 0) + self._varint_field(3, 5))
        else:
            rng = self._len(1, b''.join(self.varint(v) for v in (zero_based, 0, 5)))
        out = rng + self._len(2, symbol.encode()) + self._varint_field(3, roles)
        if span:
            out += self._len(7, b''.join(self.varint(v) for v in (span[0] - 1, 0, span[1] - 1, 0)))
        return out

    @classmethod
    def _len(cls, field, payload):
        return cls.varint(field << 3 | 2) + cls.varint(len(payload)) + payload

    @classmethod
    def _varint_field(cls, field, value):
        return cls.varint(field << 3) + cls.varint(value)

    @staticmethod
    def varint(value):
        out = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            out.append(byte | (0x80 if value else 0))
            if not value:
                return bytes(out)
