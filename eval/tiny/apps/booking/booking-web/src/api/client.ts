import { API_URL } from "../config";

export class ApiError extends Error {
  constructor(message: string, readonly details?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

interface GraphQLResponse<T> {
  data?: T;
  errors?: { message: string }[];
}

export async function gql<T>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${API_URL}/graphql`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  if (!response.ok) {
    throw new ApiError(`GraphQL request failed with ${response.status}`);
  }
  const payload = (await response.json()) as GraphQLResponse<T>;
  if (payload.errors?.length) {
    throw new ApiError(payload.errors.map((e) => e.message).join("; "), payload.errors);
  }
  return payload.data as T;
}
