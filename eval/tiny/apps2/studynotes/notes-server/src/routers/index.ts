import { router } from '../trpc';
import { notesRouter } from './notes';
import { tagsRouter } from './tags';

export const appRouter = router({
  notes: notesRouter,
  tags: tagsRouter,
});

export type AppRouter = typeof appRouter;
