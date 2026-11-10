import { GraphQLClient, gql } from 'graphql-request';
import { env } from '@/config';

const graphql = new GraphQLClient(env.graphqlUrl);

const SEARCH_NOTES = gql`
  query SearchNotes($query: String!, $limit: Int) {
    searchNotes(query: $query, limit: $limit) {
      score
      note {
        id
        title
        tags
      }
    }
  }
`;

const SAVE_SEARCH = gql`
  mutation SaveSearch($query: String!) {
    saveSearch(query: $query) {
      id
      createdAt
    }
  }
`;

export interface SearchResult {
  score: number;
  note: { id: string; title: string; tags: string[] };
}

export async function searchNotes(query: string, limit = 5): Promise<SearchResult[]> {
  const data = await graphql.request<{ searchNotes: SearchResult[] }>(SEARCH_NOTES, { query, limit });
  return data.searchNotes;
}

export async function saveSearch(query: string) {
  const data = await graphql.request<{ saveSearch: { id: string; createdAt: string } }>(SAVE_SEARCH, {
    query,
  });
  return data.saveSearch;
}
