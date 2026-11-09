import unittest

from .support import Repository

API = """
import { getConfig } from './config';

export class ChatApi {
  constructor(private baseUrl: string = getConfig().API_URL) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, { method, body: JSON.stringify(body) });
    return res.json();
  }

  listRooms() { return this.request('GET', '/api/rooms'); }
  postMessage(roomId: string, text: string) {
    return this.request('POST', `/api/rooms/${encodeURIComponent(roomId)}/messages`, { text });
  }
}
"""
CLIENT = """
export async function apiFetch(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, { method, body });
  return res.json();
}
"""
CALLERS = """
import { apiFetch } from './client';
export const listEmployees = () => apiFetch('/api/employees/');
export const hire = (e) => apiFetch('/api/employees/', { method: 'POST', body: e });
"""
OTHER = """
function apiFetch(url) { return url; }
export const notARequest = () => apiFetch('/api/elsewhere/');
"""
NESTED = """
async function send(url, method, payload) {
  return fetch(url, { method, body: JSON.stringify(payload) });
}
function sendJson(path, method, payload) { return send(path, method, payload); }
export const createNote = (n) => sendJson('/api/notes', 'POST', n);
"""
AWAITED = """
import { http } from './http';
export async function health() {
  const { data } = await http.get<{ status: string }>('/healthz');
  return data;
}
"""


class WrapperTest(unittest.TestCase):
    def calls(self, files):
        return {(c.method, str(c.path), c.file, c.line) for c in Repository(files).extract().calls}

    def test_a_class_method_wrapper_is_settled_at_its_callers(self):
        found = self.calls({'src/api.ts': API})
        self.assertIn(('GET', '/api/rooms', 'src/api.ts', 12), found)
        self.assertIn(('POST', '/api/rooms/{roomId}/messages', 'src/api.ts', 14), found)

    def test_an_options_parameter_gives_the_method_and_its_default(self):
        found = self.calls({'src/client.ts': CLIENT, 'src/hr.ts': CALLERS, 'src/other.ts': OTHER})
        self.assertIn(('GET', '/api/employees', 'src/hr.ts', 3), found)
        self.assertIn(('POST', '/api/employees', 'src/hr.ts', 4), found)
        self.assertFalse(
            any(path == '/api/elsewhere' for _, path, _, _ in found)
        )  # a same-named function, not imported

    def test_wrappers_of_wrappers(self):
        self.assertIn(('POST', '/api/notes', 'src/notes.js', 6), self.calls({'src/notes.js': NESTED}))

    def test_typescript_generic_calls_under_await(self):
        self.assertIn(('GET', '/healthz', 'src/api/health.ts', 4), self.calls({'src/api/health.ts': AWAITED}))


if __name__ == '__main__':
    unittest.main()
