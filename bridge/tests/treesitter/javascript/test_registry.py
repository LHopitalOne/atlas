import unittest

from atlas_bridge.adapters.treesitter.javascript.calls.pending import PendingRequest
from atlas_bridge.adapters.treesitter.javascript.clients.registry import ClientRegistry
from atlas_bridge.adapters.treesitter.javascript.clients.specs import (
    ClientClass,
    ClientFactory,
    ClientSpec,
    ClientVariable,
    KnownBase,
    MadeClient,
)


class ClientRegistryTest(unittest.TestCase):
    def test_code_outside_tests_wins(self):
        registry = ClientRegistry()
        registry.add_classes({'Client': ''}, test=True)
        registry.add_classes({'Client': '/api/0'}, test=False)
        registry.add_classes({'Client': '/mock'}, test=True)
        self.assertEqual(registry.base(ClientClass('Client')), '/api/0')
        self.assertEqual(registry.class_names(), frozenset({'Client'}))

    def test_classes_with_several_defaults_have_an_unknown_base(self):
        registry = ClientRegistry()
        registry.add_classes({'Client': '/a'}, test=False)
        registry.add_classes({'Client': '/b'}, test=False)
        self.assertEqual(registry.base(ClientClass('Client')), ClientRegistry.UNKNOWN_BASE)
        self.assertIsNone(registry.base(ClientClass('Other')))

    def test_factories_and_variables_lead_to_a_class(self):
        registry = ClientRegistry()
        registry.add_classes({'Client': '/api/0'}, test=False)
        registry.add_factories({'useApi': ClientClass('Client')}, test=False)
        registry.add_variables({'API': ClientFactory('useApi')}, test=False)
        self.assertEqual(registry.base(ClientVariable('API')), '/api/0')
        self.assertEqual(registry.base(KnownBase('/given')), '/given')

    def test_cycles_and_ambiguous_factories_have_no_base(self):
        registry = ClientRegistry()
        registry.add_variables({'a': ClientVariable('b'), 'b': ClientVariable('a')}, False)
        self.assertIsNone(registry.base(ClientVariable('a')))
        registry.add_factories({'make': KnownBase('/x')}, test=False)
        registry.add_factories({'make': KnownBase('/y')}, test=False)
        self.assertIsNone(registry.base(ClientFactory('make')))

    def test_kinds_of_the_same_name_differ(self):
        self.assertNotEqual(ClientClass('x'), ClientFactory('x'))
        self.assertNotEqual(ClientFactory('x'), ClientVariable('x'))
        self.assertEqual(len({ClientClass('x'), ClientClass('x'), ClientVariable('x')}), 2)
        for spec in (KnownBase, ClientClass, ClientFactory, ClientVariable):
            self.assertTrue(issubclass(spec, ClientSpec))
        self.assertTrue(issubclass(ClientVariable, MadeClient))
        with self.assertRaises(TypeError):
            ClientSpec('x')  # abstract

    def test_prefixed(self):
        registry = ClientRegistry()
        base = KnownBase('/api/0/')
        self.assertEqual(registry.prefixed('/teams', base), '/api/0/teams')
        self.assertEqual(registry.prefixed('/api/0/teams', base), '/api/0/teams')
        self.assertEqual(registry.prefixed('/teams', KnownBase('/')), '/teams')
        self.assertEqual(registry.prefixed('/teams', ClientClass('Unknown')), '/teams')

    def test_a_request_without_a_client_keeps_its_path(self):
        pending = PendingRequest(None, 1, 'GET', '', frozenset(), False, '/teams', None)
        self.assertEqual(pending.full_path(ClientRegistry()), '/teams')
        with_client = PendingRequest(None, 1, 'GET', '', frozenset(), False, '/teams', KnownBase('/api'))
        self.assertEqual(with_client.full_path(ClientRegistry()), '/api/teams')

    def test_typed(self):
        self.assertEqual(ClientClass.typed('Client'), ClientClass('Client'))
        self.assertIsNone(ClientClass.typed(''))


if __name__ == '__main__':
    unittest.main()
