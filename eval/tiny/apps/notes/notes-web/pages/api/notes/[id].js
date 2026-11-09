import { deleteNote, getNote, updateNote } from '../../../lib/notesStore';
import { searchIndexer } from '../../../lib/searchIndexer';
import { withRequestLog } from '../../../lib/withRequestLog';

async function handler(req, res) {
  const { id } = req.query;

  switch (req.method) {
    case 'GET': {
      const note = await getNote(id);
      return note ? res.status(200).json(note) : res.status(404).json({ error: 'not found' });
    }
    case 'PUT': {
      const note = await updateNote(id, req.body || {});
      if (!note) return res.status(404).json({ error: 'not found' });
      await searchIndexer.indexNote(note);
      return res.status(200).json(note);
    }
    case 'DELETE': {
      const removed = await deleteNote(id);
      if (!removed) return res.status(404).json({ error: 'not found' });
      await searchIndexer.removeNote(id);
      return res.status(204).end();
    }
    default:
      res.setHeader('Allow', 'GET, PUT, DELETE');
      return res.status(405).end();
  }
}

export default withRequestLog('/api/notes/{id}', handler);
