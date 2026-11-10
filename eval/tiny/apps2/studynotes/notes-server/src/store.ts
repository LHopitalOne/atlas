import { randomUUID } from 'node:crypto';

export interface Note {
  id: string;
  title: string;
  body: string;
  tags: string[];
  remindAt: string | null;
  remindedAt: string | null;
  createdAt: string;
}

export interface NewNote {
  title: string;
  body: string;
  remindAt?: string | null;
}

class NoteStore {
  private notes = new Map<string, Note>();
  private savedSearches: { id: string; query: string; createdAt: string }[] = [];

  all(): Note[] {
    return [...this.notes.values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  get(id: string): Note | undefined {
    return this.notes.get(id);
  }

  insert(input: NewNote): Note {
    const note: Note = {
      id: randomUUID(),
      title: input.title,
      body: input.body,
      tags: [],
      remindAt: input.remindAt ?? null,
      remindedAt: null,
      createdAt: new Date().toISOString(),
    };
    this.notes.set(note.id, note);
    return note;
  }

  remove(id: string): boolean {
    return this.notes.delete(id);
  }

  due(before: Date): Note[] {
    return this.all().filter(
      (n) => n.remindAt !== null && n.remindedAt === null && new Date(n.remindAt) <= before,
    );
  }

  saveSearch(query: string) {
    const entry = { id: randomUUID(), query, createdAt: new Date().toISOString() };
    this.savedSearches.push(entry);
    return entry;
  }
}

export const store = new NoteStore();
