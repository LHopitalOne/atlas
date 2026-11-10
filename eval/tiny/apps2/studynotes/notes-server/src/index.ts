import { createServer } from 'node:http';
import { createHTTPServer } from '@trpc/server/adapters/standalone';
import { createYoga } from 'graphql-yoga';
import { config } from './config';
import { schema } from './graphql/schema';
import { appRouter } from './routers';
import { createContext } from './trpc';

const trpcServer = createHTTPServer({
  router: appRouter,
  basePath: '/trpc/',
  createContext,
  onError({ path, error }) {
    console.error(`tRPC error on ${path ?? '<unknown>'}: ${error.message}`);
  },
});
trpcServer.listen(config.trpcPort);
console.log(`tRPC listening on http://127.0.0.1:${config.trpcPort}/trpc`);

const yoga = createYoga({ schema, graphqlEndpoint: '/graphql', logging: false });
const graphqlServer = createServer(yoga);
graphqlServer.listen(config.graphqlPort, () => {
  console.log(`GraphQL listening on http://127.0.0.1:${config.graphqlPort}/graphql`);
});

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => {
    trpcServer.close();
    graphqlServer.close();
    process.exit(0);
  });
}
