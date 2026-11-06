"""The Protocol Buffers wire format, as much of it as reading a SCIP index needs. No protobuf package required."""

from ...core.errors import ScipFormatError


class WireReader:
    """Walks the fields of one encoded message. Values are ints (varints) or memoryviews (length-delimited);
    fixed-width fields are skipped. A malformed buffer raises ScipFormatError naming `source`."""

    VARINT, I64, LEN, I32 = 0, 1, 2, 5
    FIXED = {I64: 8, I32: 4}

    def __init__(self, source: str):
        self._source = source

    def fields(self, buf):
        """(field number, wire type, value) for every field of the message in `buf`."""
        i, end = 0, len(buf)
        while i < end:
            key, i = self.varint(buf, i)
            number, wire = key >> 3, key & 7
            if wire == self.VARINT:
                value, i = self.varint(buf, i)
            elif wire == self.LEN:
                size, i = self.varint(buf, i)
                value, i = buf[i : i + size], i + size
            elif wire in self.FIXED:
                value, i = None, i + self.FIXED[wire]
            else:
                raise ScipFormatError(self._source, f'unknown wire type {wire} at byte {i}')
            if i > end:
                raise ScipFormatError(self._source, 'a field runs past the end of its message')
            yield number, wire, value

    def varint(self, buf, i):
        """(value, next index) of the varint starting at buf[i]."""
        value = shift = 0
        try:
            while True:
                byte = buf[i]
                i += 1
                value |= (byte & 0x7F) << shift
                if byte < 0x80:
                    return value, i
                shift += 7
        except IndexError as e:
            raise ScipFormatError(self._source, 'the data ends inside a number') from e

    def ints(self, wire, value):
        """The ints of a repeated int32 field: one varint, or a packed run of them."""
        if wire == self.VARINT:
            return [value]
        out, i = [], 0
        while i < len(value):
            n, i = self.varint(value, i)
            out.append(n)
        return out
