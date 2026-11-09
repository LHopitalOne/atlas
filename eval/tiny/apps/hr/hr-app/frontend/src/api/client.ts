export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

export async function apiFetch<T>(path: string, { method = "GET", body }: RequestOptions = {}): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { Accept: "application/json", ...(body !== undefined && { "Content-Type": "application/json" }) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return (await res.json()) as T;
}
