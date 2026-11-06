import unittest

from atlas_bridge.adapters.scip import ScipSymbol, WireReader
from atlas_bridge.core.errors import ScipFormatError

from .builder import ScipBuilder


class WireReaderTest(unittest.TestCase):
    def setUp(self):
        self.reader = WireReader('test.scip')

    def test_varints(self):
        for n in (0, 1, 127, 128, 300, 2**31):
            self.assertEqual(self.reader.varint(ScipBuilder.varint(n), 0), (n, len(ScipBuilder.varint(n))))

    def test_fields_and_packed_ints(self):
        data = ScipBuilder._len(1, b''.join(ScipBuilder.varint(v) for v in (4, 2, 9))) + ScipBuilder._varint_field(3, 7)
        fields = list(self.reader.fields(data))
        self.assertEqual([(f, w) for f, w, _ in fields], [(1, 2), (3, 0)])
        self.assertEqual(self.reader.ints(2, fields[0][2]), [4, 2, 9])
        self.assertEqual(self.reader.ints(0, 5), [5])

    def test_fixed_width_fields_are_skipped(self):
        data = bytes([1 << 3 | 1]) + bytes(8) + bytes([2 << 3 | 5]) + bytes(4) + ScipBuilder._varint_field(3, 1)
        self.assertEqual([(f, v) for f, _, v in self.reader.fields(data)], [(1, None), (2, None), (3, 1)])

    def test_malformed(self):
        for bad in (bytes([0x80]), bytes([1 << 3 | 2, 5, 1]), bytes([1 << 3 | 3])):
            with self.assertRaises(ScipFormatError):
                list(self.reader.fields(bad))


class ScipSymbolTest(unittest.TestCase):
    def test_names(self):
        cases = {
            'scip-python python sentry 0.0.0 `src.sentry.utils.snuba`/_snuba_pool.': '_snuba_pool',
            'scip-python python sentry 0.0.0 `a.b`/Symbolicator#_process().': '_process',
            'scip-python python sentry 0.0.0 `a.b`/Symbolicator#process_payload().(self)': 'self',
            'rust-analyzer cargo relay-server 26.10.1 services/upstream/UpstreamQuery#': 'UpstreamQuery',
            'rust-analyzer cargo relay 1.0 lib/Thing#[T]': 'T',
            'rust-analyzer cargo relay 1.0 macros/format!': 'format',
            'scip-typescript npm web 1.0 src/`api.js`/placeOrder().': 'placeOrder',
            'scip-typescript npm web 1.0 src/`api.js`/': 'api.js',
            'x y z 1 `odd``name`.': 'odd`name',
            'local 12': '',
            '': '',
        }
        for symbol, name in cases.items():
            self.assertEqual(ScipSymbol.name(symbol), name, symbol)


if __name__ == '__main__':
    unittest.main()
