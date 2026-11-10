import { createTRPCClient, httpBatchLink } from '@trpc/client';
import type { AppRouter } from '@studynotes/server';
import { env } from '@/config';

export const trpc = createTRPCClient<AppRouter>({
  links: [
    httpBatchLink({
      url: `${env.apiUrl}/trpc`,
      headers: () => ({ 'x-client': 'notes-web' }),
    }),
  ],
});
