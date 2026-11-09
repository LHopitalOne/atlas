import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import { removeNote, saveNote } from '../../lib/api';

export default function NotePage() {
  const router = useRouter();
  const { id } = router.query;
  const { data: note, error, mutate } = useSWR(id ? `/api/notes/${id}` : null);
  const [draft, setDraft] = useState({ title: '', body: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (note) setDraft({ title: note.title, body: note.body });
  }, [note]);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await saveNote(id, draft);
      mutate(updated, false);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm('Delete this note?')) return;
    await removeNote(id);
    router.push('/');
  }

  if (error) return <p>Note not found.</p>;
  if (!note) return <p>Loading…</p>;

  return (
    <main>
      <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
      <textarea value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
      <button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
      <button onClick={handleDelete}>Delete</button>
    </main>
  );
}
