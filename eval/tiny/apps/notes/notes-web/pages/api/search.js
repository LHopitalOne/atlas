import { searchIndexer } from '../../lib/searchIndexer';
import { withRequestLog } from '../../lib/withRequestLog';

async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).end();
  }
  const q = String(req.query.q || '').trim();
  if (!q) return res.status(200).json([]);

  try {
    const hits = await searchIndexer.search(q, Number(req.query.limit) || 10);
    return res.status(200).json(hits);
  } catch (err) {
    return res.status(502).json({ error: 'search unavailable' });
  }
}

export default withRequestLog('/api/search', handler);
