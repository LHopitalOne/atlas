import unittest

from .support import extract


class PayloadTest(unittest.TestCase):
    def test_reverse_names_and_hints(self):
        ex = extract(
            {
                'src/app/native/sources.py': """
                '''Symbol sources.'''
                from django.urls import reverse

                def get_internal_source(project):
                    '''Internal callers (e.g. Relay) get another URL.'''
                    url = '{}{}'.format(prefix(), reverse('dsym-files', kwargs={'org': project.org}))
                    return {'type': 'internal', 'url': url, 'service': 'symbolicator-source'}

                def get_sources(project):
                    relay_state = request.POST.get('RelayState')
                    return [get_internal_source(project)]

                def lookup_url(project):
                    return reverse('artifact-lookup')

                def lookup_source(project):
                    return {'url': lookup_url(project)}

                reverse(name_var)
                urls.reverse(viewname='module-level')
                items.reverse()
                reverse(f'{prefix}-x')
                """,
                'src/app/native/symbolicator.py': """
                from app.native.sources import lookup_source

                class Symbolicator:
                    def process_js(self):
                        return lookup_source(self.project)
                """,
                'tests/test_views.py': """
                from app.native.sources import lookup_source

                def test_view(client):
                    client.get(reverse('dsym-files'))

                def test_lookup():
                    lookup_source(None)
                """,
            }
        )
        payloads = {(c.route_name, c.test) for c in ex.calls if c.kind == 'payload'}
        self.assertEqual(
            payloads, {('dsym-files', False), ('artifact-lookup', False), ('module-level', False), ('dsym-files', True)}
        )
        dsym = next(c for c in ex.calls if c.route_name == 'dsym-files' and not c.test)
        self.assertIsNone(dsym.path)
        self.assertIn('symbolicator-source', dsym.hints)
        self.assertIn('get_sources', dsym.hints)
        self.assertIn("'''Symbol sources.'''", dsym.hints)
        self.assertFalse({'relay_state', 'RelayState'} & dsym.hints)  # a caller's own words name services by chance
        self.assertFalse(any('Relay)' in h for h in dsym.hints))  # the function's docstring is prose about others
        lookup = next(c for c in ex.calls if c.route_name == 'artifact-lookup')
        self.assertIn('src/app/native/symbolicator.py', lookup.hints)
        self.assertIn('Symbolicator.process_js', lookup.hints)
        self.assertNotIn('tests/test_views.py', lookup.hints)
        self.assertNotIn('test_lookup', lookup.hints)
