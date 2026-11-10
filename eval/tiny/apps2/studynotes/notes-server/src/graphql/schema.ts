import { createSchema } from 'graphql-yoga';
import { indexer } from '../clients/indexer';
import { recv } from '../observe';
import { store } from '../store';

const typeDefs = /* GraphQL */ `
  type Note {
    id: ID!
    title: String!
    body: String!
    tags: [String!]!
  }

  type SearchResult {
    score: Float!
    note: Note!
  }

  type SavedSearch {
    id: ID!
    query: String!
    createdAt: String!
  }

  type Query {
    searchNotes(query: String!, limit: Int = 10): [SearchResult!]!
  }

  type Mutation {
    saveSearch(query: String!): SavedSearch!
  }
`;

export const schema = createSchema({
  typeDefs,
  resolvers: {
    Query: {
      searchNotes: async (_parent: unknown, args: { query: string; limit: number }) => {
        recv('T07', `graphql QUERY searchNotes query=${JSON.stringify(args.query)}`);
        const hits = await indexer.search(args.query, args.limit);
        return hits.flatMap((hit) => {
          const note = store.get(hit.noteId);
          return note ? [{ score: hit.score, note }] : [];
        });
      },
    },
    Mutation: {
      saveSearch: (_parent: unknown, args: { query: string }) => {
        recv('T08', `graphql MUTATION saveSearch query=${JSON.stringify(args.query)}`);
        return store.saveSearch(args.query);
      },
    },
  },
});
