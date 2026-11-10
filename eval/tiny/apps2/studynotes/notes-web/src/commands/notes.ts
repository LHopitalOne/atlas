import { trpc } from '@/lib/trpc';

export interface DraftNote {
  title: string;
  body: string;
  remindInMinutes?: number;
}

export async function createNote(draft: DraftNote) {
  const remindAt =
    draft.remindInMinutes === undefined
      ? null
      : new Date(Date.now() + draft.remindInMinutes * 60_000).toISOString();
  return trpc.notes.create.mutate({ title: draft.title, body: draft.body, remindAt });
}

export function listNotes() {
  return trpc.notes.list.query();
}

export function openNote(id: string) {
  return trpc.notes.byId.query({ id });
}

export async function deleteNote(id: string) {
  const { removed } = await trpc.notes.delete.mutate({ id });
  return removed;
}
