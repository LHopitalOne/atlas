import unittest

from atlas_bridge.adapters.treesitter.python.routes import DjangoRegex, FlaskPath


class RegexTemplateTest(unittest.TestCase):
    def test_named_groups_anchors_and_optional_tails(self):
        t = DjangoRegex.templates
        self.assertEqual(t(r'^(?P<org>[^/]+)/(?P<proj>[^/]+)/files/dsyms/$'), ['{org}/{proj}/files/dsyms/'])
        self.assertEqual(t(r'^api/client-config/?$'), ['api/client-config'])
        self.assertEqual(t(r'^api/relay/.*$'), ['api/relay/{*path}'])
        self.assertEqual(t(r'^(?:issues|groups)/'), ['issues/', 'groups/'])
        self.assertEqual(t(r'^robots\.txt$'), ['robots.txt'])
        self.assertEqual(t(r'^(?P<path>.*)$'), ['{*path}'])
        self.assertEqual(t(r'^(\d+)/x(?:/extra)?/$'), ['{param}/x/'])
        self.assertEqual(t(r'^v\d+/[a-z]+/(?=x)(?i)y\b$'), ['v{param}/{param}/y'])
        self.assertEqual(t(r'^(?P<id>(?:a|\d+))/(?P=id)/\w*/z{1,2}/e?$'), ['{id}/{param}/{param}/z/'])
        self.assertEqual(t(r'^a|b$'), ['a', 'b'])
        self.assertEqual(t(r'^[]x]/[^]]/(a'), ['{param}/{param}/{param}'])
        self.assertEqual(t(r'^(?P<p>[)(])/(?:[)]|b)/(?P<q>[^]\])]+)$'), ['{p}/{param}/{q}', '{p}/b/{q}'])

    def test_wildcards_and_limits(self):
        t = DjangoRegex.templates
        self.assertEqual(t(r'^(.+)/x$'), ['{*param}/x'])
        self.assertEqual(t(r'^\d?/y$'), ['/y'])
        self.assertEqual(t(r'^[a-z'), ['{param}'])
        self.assertEqual(t(''), [''])
        self.assertEqual(len(t('(?:a|b|c)(?:d|e|f)(?:g|h|i)')), DjangoRegex.MAX_ALTS)


class FlaskPathTest(unittest.TestCase):
    def test_flask_converters(self):
        self.assertEqual(FlaskPath.template('/a/<int:id>/<path:rest>/<name>'), '/a/{id}/{*rest}/{name}')
        self.assertEqual(FlaskPath.template('/f/{p:path}/{n:int}'), '/f/{*p}/{n}')
