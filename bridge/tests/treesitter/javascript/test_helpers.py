"""Request helpers: options objects read by member access, helpers passed by reference, URLs assigned in branches."""

import unittest

from .support import Repository

OPTIONS = """
import $ from 'jquery';
export function get(options) {
  return $.ajax({ url: options.url, type: 'GET', data: options.data });
}
"""
OPTIONS_CALLER = """
import { get } from './http';
export const items = () => get({ url: '/api/items', data: {} });
export const nothing = () => get({ data: {} });
"""
CLIENT = """
import $ from 'jquery';
function call(args) {
  if (!args.url) return undefined;
  return $.ajax(args);
}
export function patch(options) {
  const args = { type: 'PATCH', dataType: 'json', ...options };
  return call(args);
}
export function del(options) {
  const args = { type: 'DELETE', ...options };
  return call(args);
}
"""
CLIENT_CALLERS = """
import * as client from './client';
export function rename(id) {
  client.patch({ url: `/api/rooms/${id}`, data: { name: 'x' } });
  client.patch({ url: '/api/rooms', type: 'PUT' });
}
"""
DIALOG = """
export function submit(send, url, data) {
  open();
  send({ url, data, success() { close(); } });
}
"""
DIALOG_CALLERS = """
import * as client from './client';
import * as dialog from './dialog';
import { submit } from './dialog';
export function remove(id) {
  const url = '/api/rooms/' + encodeURIComponent(id);
  dialog.submit(client.del, url, {});
  submit(client.patch, '/api/settings', {});
}
"""
LOCAL_HANDOFF = """
function post(options) { return fetch(options.url, { method: 'POST' }); }
function run(request, path) { return request({ url: path }); }
export const go = () => run(post, '/api/jobs');
export const other = () => run(somethingElse, '/api/unknown');
"""
BRANCHES = """
export function revoke(id, multi) {
  let url = '/api/invites/' + id;
  if (multi) {
    url = '/api/invites/multi/' + id;
  }
  fetch(url, { method: 'DELETE' });
  url = '/api/later/' + id;
}
"""
UPDATED = """
export function load(id) {
  let url = '/api/items';
  url += '/' + id;
  fetch(url);
}
"""
REBUILT = """
export function load(id, q) {
  let url = '/api/items';
  url = url + '/' + id;
  fetch(url);
}
"""
REPLACED = """
export function load(id, all) {
  let url = '/api/old';
  url = '/api/items/' + id;
  if (all) url = '/api/all';
  fetch(url);
}
"""


class HelperTest(unittest.TestCase):
    def calls(self, files):
        return {(c.method, str(c.path), c.file, c.line) for c in Repository(files).extract().calls}

    def test_an_options_parameter_read_by_member_access(self):
        found = self.calls({'src/http.js': OPTIONS, 'src/items.js': OPTIONS_CALLER})
        self.assertEqual({('GET', '/api/items', 'src/items.js', 3)}, found)

    def test_settings_spread_into_a_wrapper_keep_the_wrappers_method_unless_the_caller_gives_one(self):
        found = self.calls({'src/client.js': CLIENT, 'src/rooms.js': CLIENT_CALLERS})
        self.assertEqual(
            {('PATCH', '/api/rooms/{id}', 'src/rooms.js', 4), ('PUT', '/api/rooms', 'src/rooms.js', 5)}, found
        )

    def test_a_helper_passed_by_reference_is_called_where_its_parameter_is(self):
        files = {'src/client.js': CLIENT, 'src/dialog.js': DIALOG, 'src/rooms.js': DIALOG_CALLERS}
        found = self.calls(files)
        self.assertIn(('DELETE', '/api/rooms/{id}', 'src/rooms.js', 7), found)
        self.assertIn(('PATCH', '/api/settings', 'src/rooms.js', 8), found)
        self.assertEqual(2, len(found))

    def test_a_local_function_passed_by_reference(self):
        self.assertEqual({('POST', '/api/jobs', 'src/jobs.js', 4)}, self.calls({'src/jobs.js': LOCAL_HANDOFF}))

    def test_each_value_a_let_is_assigned_before_the_request(self):
        found = self.calls({'src/invites.js': BRANCHES})
        self.assertEqual(
            {
                ('DELETE', '/api/invites/{id}', 'src/invites.js', 7),
                ('DELETE', '/api/invites/multi/{id}', 'src/invites.js', 7),
            },
            found,
        )

    def test_a_let_changed_in_place_reads_as_before(self):
        self.assertEqual({('GET', '/api/items', 'src/items.js', 5)}, self.calls({'src/items.js': UPDATED}))

    def test_a_let_rebuilt_from_itself_reads_as_before(self):
        self.assertEqual({('GET', '/api/items', 'src/items.js', 5)}, self.calls({'src/items.js': REBUILT}))

    def test_a_value_replaced_unconditionally_is_not_a_request(self):
        found = {(m, p) for m, p, _, _ in self.calls({'src/items.js': REPLACED})}
        self.assertEqual({('GET', '/api/items/{id}'), ('GET', '/api/all')}, found)


if __name__ == '__main__':
    unittest.main()
