import { initTRPC } from '@trpc/server';
import type { CreateHTTPContextOptions } from '@trpc/server/adapters/standalone';
import { recvProcedure } from './observe';

export function createContext({ req }: CreateHTTPContextOptions) {
  return { userAgent: req.headers['user-agent'] ?? 'unknown' };
}

export type Context = Awaited<ReturnType<typeof createContext>>;

const t = initTRPC.context<Context>().create();

const logged = t.middleware(async ({ path, type, next }) => {
  recvProcedure(path, type);
  return next();
});

export const router = t.router;
export const publicProcedure = t.procedure.use(logged);
