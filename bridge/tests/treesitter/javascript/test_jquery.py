import unittest

from .support import Repository

JQUERY = """
import jq from 'jquery';
export function load(id) {
  $.ajax({ url: '/api/a', type: 'POST' });
  $.ajax('/api/b', { method: 'PUT' });
  $.get('/api/c');
  $.post('/api/d', { id });
  $.getJSON('/api/e');
  jQuery.ajax({ url: '/api/f' });
  jq.post('/api/g');
  window.$.ajax({ url: `/api/h/${id}`, method: 'DELETE' });
  $.get({ url: '/api/i' });
  $.ajax('relative/page.html');
}
"""
NOT_JQUERY = """
import $ from 'cash-dom';
$.ajax({ url: '/api/z' });
"""
SHADOWED = """
function local($) { return $.ajax({ url: '/api/shadowed' }); }
"""
SETTINGS = """
const settings = { url: '/api/settings', type: 'PATCH' };
$.ajax(settings);
"""


class JQueryTest(unittest.TestCase):
    def calls(self, files):
        return {(c.method, str(c.path), c.file, c.line) for c in Repository(files).extract().calls}

    def test_the_request_functions_of_jquery(self):
        found = {(m, p) for m, p, _, _ in self.calls({'src/page.js': JQUERY})}
        expected = {
            ('POST', '/api/a'),
            ('PUT', '/api/b'),
            ('GET', '/api/c'),
            ('POST', '/api/d'),
            ('GET', '/api/e'),
            ('GET', '/api/f'),
            ('POST', '/api/g'),
            ('DELETE', '/api/h/{id}'),
            ('GET', '/api/i'),
        }
        self.assertEqual(expected, found)

    def test_another_library_or_a_local_dollar_is_not_jquery(self):
        self.assertEqual(set(), self.calls({'src/a.js': NOT_JQUERY, 'src/b.js': SHADOWED}))

    def test_settings_held_by_a_const(self):
        self.assertEqual({('PATCH', '/api/settings', 'src/a.js', 3)}, self.calls({'src/a.js': SETTINGS}))


if __name__ == '__main__':
    unittest.main()
