export async function fetcher(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const error = new Error(`Request to ${url} failed`);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

async function send(url, method, payload) {
  const res = await fetch(url, {
    method,
    headers: payload ? { 'Content-Type': 'application/json' } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${url} failed with ${res.status}`);
  return res.status === 204 ? null : res.json();
}

export function createNote(note) {
  return send('/api/notes', 'POST', note);
}

export function saveNote(id, changes) {
  return send(`/api/notes/${id}`, 'PUT', changes);
}

export function removeNote(id) {
  return send(`/api/notes/${id}`, 'DELETE');
}
