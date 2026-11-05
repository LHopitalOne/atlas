import unittest

from atlas_bridge.adapters.treesitter.rust.attributes import TestAttributes
from atlas_bridge.adapters.treesitter.rust.names import ItemPath
from atlas_bridge.adapters.treesitter.rust.policy import RustTestPolicy


class TestAttributesTest(unittest.TestCase):
    def test_test_attributes(self):
        for attr in ('test', 'tokio::test(flavor = "x")', 'rstest', 'test_case(1)', 'cfg(test)', 'cfg(all(test, a))'):
            self.assertTrue(TestAttributes.is_test(attr), attr)

    def test_other_attributes(self):
        for attr in ('inline', 'cfg(feature = "x")', 'cfg(all(not(test), a))', 'cfg(any(test, a))', 'derive(Debug)'):
            self.assertFalse(TestAttributes.is_test(attr), attr)

    def test_top_level_args(self):
        self.assertEqual(TestAttributes.top_level_args('a,b(c,d),e'), ['a', 'b(c,d)', 'e'])


class ItemPathTest(unittest.TestCase):
    def test_strip_generics(self):
        self.assertEqual(ItemPath.strip_generics('Foo<Option<T>>'), 'Foo')
        self.assertEqual(ItemPath.strip_generics('a<b'), 'a<b')

    def test_words(self):
        self.assertEqual(ItemPath.words('UpstreamQuery'), 'Upstream Query')
        self.assertEqual(ItemPath.words('HTTPClient'), 'HTTP Client')
        self.assertEqual(ItemPath.words('Thing'), '')


class RustTestPolicyTest(unittest.TestCase):
    def test_test_paths(self):
        policy = RustTestPolicy()
        self.assertTrue(policy.is_test('crates/server-test/src/lib.rs'))
        self.assertTrue(policy.is_test('src/mocks/a.rs'))
        self.assertTrue(policy.is_test('tests/it.rs'))
        self.assertTrue(policy.is_test('src/a_test.rs'))
        self.assertFalse(policy.is_test('src/contest/a.rs'))
        self.assertFalse(policy.is_test('src/app.rs'))


if __name__ == '__main__':
    unittest.main()
