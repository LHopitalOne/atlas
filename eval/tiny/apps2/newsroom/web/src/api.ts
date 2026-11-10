import { client } from './generated/client.gen';

export const DEFAULT_API_URL = 'http://127.0.0.1:8000';

/** Point the generated OpenAPI client at the newsroom api. */
export function configureApi(baseUrl: string = DEFAULT_API_URL): void {
  client.setConfig({ baseUrl: baseUrl.replace(/\/+$/, '') });
}
