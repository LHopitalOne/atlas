import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { createNote } from '../lib/api';

export default function Home() {
  const { data: notes, error, mutate } = useSWR('/api/notes');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (!title.trim()) return;
    await createNote({ title, body });
    setTitle('');
    setBody('');
    mutate();
  }

  return (
    <main>
      <h1>Notes</h1>
      <p><Link href="/search">Search notes</Link></p>
      <form onSubmit={handleSubmit}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write something" />
        <button type="submit">Add note</button>
      </form>
      {error && <p>Could not load notes.</p>}
      {!notes && !error && <p>Loading…</p>}
      <ul>
        {notes?.map((note) => (
          <li key={note.id}>
            <Link href={`/notes/${note.id}`}>{note.title}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
