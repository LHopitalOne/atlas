const DEFAULT_BASE_URL = 'http://127.0.0.1:41602';

export class SearchIndexerError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export class SearchIndexerClient {
  constructor(baseUrl = process.env.SEARCH_INDEXER_URL || DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  async request(path, { method = 'GET', body } = {}) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      throw new SearchIndexerError(res.status, `search-indexer ${method} ${path} failed: ${res.status}`);
    }
    return res.status === 204 ? null : res.json();
  }

  indexNote(note) {
    return this.request('/index', {
      method: 'POST',
      body: { id: note.id, title: note.title, body: note.body },
    });
  }

  async removeNote(id) {
    try {
      await this.request(`/index/${encodeURIComponent(id)}`, { method: 'DELETE' });
    } catch (err) {
      if (err.status !== 404) throw err;
    }
  }

  search(query, limit = 10) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return this.request(`/search?${params}`);
  }
}

export const searchIndexer = new SearchIndexerClient();
