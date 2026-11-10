import { TRPCError } from '@trpc/server';
import { z } from 'zod';
import { store } from '../store';
import { publicProcedure, router } from '../trpc';

export const tagsRouter = router({
  list: publicProcedure.query(() => {
    const counts = new Map<string, number>();
    for (const note of store.all()) {
      for (const tag of note.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    return [...counts.entries()].map(([name, count]) => ({ name, count }));
  }),

  attach: publicProcedure
    .input(z.object({ noteId: z.string(), tags: z.array(z.string().min(1)) }))
    .mutation(({ input }) => {
      const note = store.get(input.noteId);
      if (!note) throw new TRPCError({ code: 'NOT_FOUND' });
      note.tags = [...new Set([...note.tags, ...input.tags])];
      return note;
    }),
});
