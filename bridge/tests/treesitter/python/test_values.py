import textwrap
import unittest

from atlas_bridge.adapters.treesitter.python.scope import Scope
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.values import Marker, PythonValueResolver, UrlShape, Value

from .support import workspace

SOURCE = """
HOST = 'http://h'
PARTS = ['', 'a']

def f(p, flag):
    if (x := '/w'):
        pass
    y = '/one'
    y = '/two'
    many = '/m'
    many = '/n'
    values = [
        f'{y}/{many}',
        str(p),
        cast(str, '/c'),
        HOST.rstrip('/') + '/s',
        '{0}/{1}/{name}/{x.y}/{z[0]}'.format('/a', 'b', name='n'),
        '{}{}'.format(),
        'a' 'b',
        r'\\d',
        '\\n\\q',
        f'{{x}}{p!r}',
        x,
        (),
        1 - 2,
        url_join(HOST, 'u'),
        g(),
        ''.join(PARTS),
        '/'.join([HOST, p]),
        '%s/x' % HOST,
        ('/paren'),
        '/a' if flag else '/b',
    ]
"""


class ResolverTest(unittest.TestCase):
    def setUp(self):
        self.ws = workspace({'m.py': textwrap.dedent(SOURCE)})
        self.source = self.ws.source('m.py')
        self.resolver = PythonValueResolver(self.ws)
        lst = next(
            n
            for n in PythonSyntax.walk(self.source.root, ('list',))
            if n.parent.type == 'assignment' and PythonSyntax.text(n.parent.child_by_field_name('left')) == 'values'
        )
        self.items = lst.named_children

    def texts(self, i):
        scope = Scope.at(self.source, self.items[i])
        return [Marker.braces(v.text) for v in self.resolver.resolve(self.items[i], scope)]

    def test_expression_forms(self):
        self.assertEqual(self.texts(0), ['{y}/{many}'])  # reassigned names stay placeholders in f-strings
        self.assertEqual(self.texts(1), ['{p}'])
        self.assertEqual(self.texts(2), ['/c'])
        self.assertEqual(self.texts(3), ['http://h/s'])
        self.assertEqual(self.texts(4), ['/a/b/n/{x}/{z}'])
        self.assertEqual(self.texts(5), ['{param}{param}'])
        self.assertEqual(self.texts(6), ['ab'])
        self.assertEqual(self.texts(7), ['\\d'])
        self.assertEqual(self.texts(8), ['\n\\q'])
        self.assertEqual(self.texts(9), ['{x}{p}'])
        self.assertEqual(self.texts(10), ['/w'])
        self.assertEqual(self.texts(11), ['{param}'])
        self.assertEqual(self.texts(12), ['{param}'])
        self.assertEqual(self.texts(13), ['http://h/u'])
        self.assertEqual(self.texts(14), ['{g}'])
        self.assertEqual(self.texts(15), ['{PARTS}'])
        self.assertEqual(self.texts(16), ['http://h/{p}'])
        self.assertEqual(self.texts(17), ['{}/x'])
        self.assertEqual(self.texts(18), ['/paren'])
        self.assertEqual(self.texts(19), ['/a', '/b'])

    def test_unknown_and_depth(self):
        self.assertEqual(self.resolver.resolve(None, Scope.module(self.source))[0].text, '{param}')
        deep = self.resolver.resolve(self.items[18], Scope.module(self.source), depth=99)[0]
        self.assertTrue(deep.is_unknown)


class ValueTest(unittest.TestCase):
    def test_kinds_and_markers(self):
        v = Value(Marker.wrap('p') + '/x', kind=Value.PARAM)
        self.assertTrue(v.is_param and v.is_known and not v.is_literal and not v.is_unknown)
        self.assertEqual(Marker.names(v.text), {'p'})
        self.assertEqual(Marker.braces(v.text), '{p}/x')
        self.assertEqual(Marker.fill(v.text, {}), '\x00/x')
        self.assertTrue(Marker.is_open(v.text))
        self.assertTrue(Marker.is_open(Marker.CHOICE + '0'))
        self.assertFalse(Marker.is_open('GET'))

    def test_url_shapes(self):
        self.assertEqual(UrlShape.render('{base_url}ip'), '{base_url}/ip')
        self.assertEqual(UrlShape.render('{name}ip'), '{name}ip')
        self.assertEqual(UrlShape.split('http://h:1/p?q').path, '/p')
        self.assertTrue(UrlShape.base_ok(Value('{}?x'), ''))
        self.assertFalse(UrlShape.base_ok(Value('{}_state'), 'name'))
        self.assertTrue(UrlShape.pathlike('{}/x', [], False, 1))
        self.assertFalse(UrlShape.pathlike('{}/{db}', [], False, 0))
        self.assertTrue(UrlShape.pathlike('{}x', [], True, 0))
