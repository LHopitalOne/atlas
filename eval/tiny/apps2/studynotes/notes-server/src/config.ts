export const config = {
  trpcPort: Number(process.env.TRPC_PORT ?? 45010),
  graphqlPort: Number(process.env.GRAPHQL_PORT ?? 45011),
  indexerAddr: process.env.INDEXER_ADDR ?? '127.0.0.1:45020',
};
