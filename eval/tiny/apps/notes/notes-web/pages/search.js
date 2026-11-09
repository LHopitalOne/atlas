import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const key = query.trim() ? `/api/search?q=${encodeURIComponent(query.trim())}` : null;
  const { data: hits, isLoading } = useSWR(key, { keepPreviousData: true });

  return (
    <main>
      <h1>Search</h1>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search notes" autoFocus />
      {isLoading && <p>Searching…</p>}
      <ul>
        {hits?.map((hit) => (
          <li key={hit.id}>
            <Link href={`/notes/${hit.id}`}>{hit.title}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
