import time
import unittest

from .support import Repository

calls = Repository.calls


class TestFlagTest(unittest.TestCase):
    def test_test_code(self):
        source = "describe('x', () => { it('y', async () => { await fetch('/a/b'); }); });\nfetch('/c');\n"
        found = calls(source)
        self.assertTrue(found[('GET', '/a/b')].test)
        self.assertFalse(found[('GET', '/c')].test)
        self.assertTrue(calls("fetch('/c');", 'src/a.spec.ts')[('GET', '/c')].test)
        self.assertTrue(calls("fetch('/c');", '__tests__/a.js')[('GET', '/c')].test)
        found = calls("describe.each([1])('x', () => fetch('/e'));\n!function (w) { fetch('/iife'); }(window);\n")
        self.assertTrue(found[('GET', '/e')].test)
        self.assertFalse(found[('GET', '/iife')].test)

    def test_long_receivers_are_cheap(self):
        source = '(function(){' + 'var aN=g(h(k(N)));' * 20000 + '})().client.get("/y");' + 'api.get("/z");' * 2000
        start = time.perf_counter()
        found = calls(source)
        self.assertLess(time.perf_counter() - start, 3)
        self.assertEqual(sorted(found), [('GET', '/y'), ('GET', '/z')])


if __name__ == '__main__':
    unittest.main()
