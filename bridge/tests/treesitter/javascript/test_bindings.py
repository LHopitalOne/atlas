import unittest

from atlas_bridge.adapters.treesitter.javascript.bindings.binding import Binding, ParamBinding, ValueBinding
from atlas_bridge.adapters.treesitter.javascript.syntax.nodes import JsSyntax
from atlas_bridge.adapters.treesitter.javascript.values.urls import UrlText

from .support import Repository

SOURCE = (
    "const base = '/api';\n"
    'function load(api: Client, {org}: {org: string}) {\n'
    '  const {team} = props;\n'
    '  return [base, api, org, team, missing];\n'
    '}\n'
)


class BindingTest(unittest.TestCase):
    def setUp(self):
        ws = Repository.workspace([('src/a.ts', SOURCE)])
        self.module = ws.module(ws.sources[0])
        array = next(JsSyntax.walk(self.module.source.root, {'array'}))
        self.names = {JsSyntax.text(n): n for n in array.named_children}

    def binding(self, name):
        return self.module.scopes.binding(self.names[name], name)

    def test_a_declaration_binds_its_value(self):
        binding = self.binding('base')
        self.assertIsInstance(binding, ValueBinding)
        self.assertEqual(JsSyntax.text(binding.initializer), "'/api'")
        self.assertEqual(binding.annotated_type('base'), '')
        self.assertIs(self.module.scopes.lookup(self.names['base'], 'base'), binding.initializer)

    def test_parameters_and_destructuring_bind_no_value(self):
        for name, annotated in (('api', 'Client'), ('org', ''), ('team', '')):
            binding = self.binding(name)
            self.assertIsInstance(binding, ParamBinding, name)
            self.assertIsInstance(binding, Binding)
            self.assertIsNone(binding.initializer)
            self.assertIsNone(self.module.scopes.lookup(self.names[name], name))
            self.assertEqual(binding.annotated_type(name), annotated, name)

    def test_unbound_names(self):
        self.assertIsNone(self.binding('missing'))

    def test_outer_parent_skips_wrappers(self):
        new = next(JsSyntax.walk(Repository.workspace([('a.ts', 'const x = (await (new C()));\n')]).sources[0].root,
                                 {'new_expression'}))  # fmt: skip
        self.assertEqual(JsSyntax.outer_parent(new).type, 'variable_declarator')


class UrlTextTest(unittest.TestCase):
    def test_base_names(self):
        for name in ('API_URL', 'baseUrl', 'HOST', 'SENTRY'):
            self.assertTrue(UrlText.is_base_name(name), name)
        for name in ('', 'org', 'team'):
            self.assertFalse(UrlText.is_base_name(name), name)
        self.assertTrue(UrlText.path_like('{API_URL}/x'))
        self.assertFalse(UrlText.path_like('{}/x'))
        self.assertFalse(UrlText.path_like('{org}/x'))


if __name__ == '__main__':
    unittest.main()
