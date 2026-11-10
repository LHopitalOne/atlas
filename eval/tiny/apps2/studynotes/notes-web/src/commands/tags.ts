import { trpc } from '@/lib/trpc';

export const tagCommands = {
  list: () => trpc.tags.list.query(),
  attach: (noteId: string, tags: string[]) => trpc.tags.attach.mutate({ noteId, tags }),
};
