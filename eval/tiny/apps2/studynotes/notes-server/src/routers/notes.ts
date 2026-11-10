import { TRPCError } from '@trpc/server';
import { z } from 'zod';
import { indexer } from '../clients/indexer';
import { store } from '../store';
import { publicProcedure, router } from '../trpc';

const noteInput = z.object({
  title: z.string().min(1),
  body: z.string(),
  remindAt: z.string().datetime().nullish(),
});

export const notesRouter = router({
  list: publicProcedure.query(() => store.all()),

  byId: publicProcedure.input(z.object({ id: z.string() })).query(({ input }) => {
    const note = store.get(input.id);
    if (!note) throw new TRPCError({ code: 'NOT_FOUND', message: `note ${input.id} not found` });
    return note;
  }),

  create: publicProcedure.input(noteInput).mutation(async ({ input }) => {
    const note = store.insert(input);
    const { termCount } = await indexer.indexNote(note.id, note.title, note.body);
    return { ...note, termCount };
  }),

  delete: publicProcedure.input(z.object({ id: z.string() })).mutation(({ input }) => {
    const removed = store.remove(input.id);
    if (removed) indexer.removeNote(input.id);
    return { removed };
  }),

  due: publicProcedure
    .input(z.object({ before: z.string().datetime() }))
    .query(({ input }) => store.due(new Date(input.before))),

  markReminded: publicProcedure
    .input(z.object({ ids: z.array(z.string()) }))
    .mutation(({ input }) => {
      const now = new Date().toISOString();
      let updated = 0;
      for (const id of input.ids) {
        const note = store.get(id);
        if (note && note.remindedAt === null) {
          note.remindedAt = now;
          updated += 1;
        }
      }
      return { updated };
    }),
});
