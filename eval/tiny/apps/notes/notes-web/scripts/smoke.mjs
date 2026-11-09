const base = process.env.NOTES_WEB_URL || 'http://127.0.0.1:41601';

async function call(method, path, body) {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  console.log(`${method} ${path} -> ${res.status}`);
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

await call('GET', '/api/notes');
const note = await call('POST', '/api/notes', { title: 'Grocery list', body: 'milk eggs coffee' });
await call('GET', `/api/notes/${note.id}`);
await call('PUT', `/api/notes/${note.id}`, { body: 'milk eggs coffee bananas' });
const hits = await call('GET', '/api/search?q=bananas');
if (!hits.some((h) => h.id === note.id)) throw new Error('search did not return the saved note');
await call('DELETE', `/api/notes/${note.id}`);
console.log('smoke ok');
