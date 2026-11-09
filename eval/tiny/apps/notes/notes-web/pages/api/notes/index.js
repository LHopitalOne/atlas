import { createNote, listNotes } from '../../../lib/notesStore';
import { searchIndexer } from '../../../lib/searchIndexer';
import { withRequestLog } from '../../../lib/withRequestLog';

async function handler(req, res) {
  if (req.method === 'GET') {
    return res.status(200).json(await listNotes());
  }

  if (req.method === 'POST') {
    const { title, body } = req.body || {};
    if (!title || typeof title !== 'string') {
      return res.status(400).json({ error: 'title is required' });
    }
    const note = await createNote({ title, body });
    try {
      await searchIndexer.indexNote(note);
    } catch (err) {
      console.error('indexing failed', err.message);
    }
    return res.status(201).json(note);
  }

  res.setHeader('Allow', 'GET, POST');
  return res.status(405).end();
}

export default withRequestLog('/api/notes', handler);
