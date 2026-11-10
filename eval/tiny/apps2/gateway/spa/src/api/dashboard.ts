import { http } from './client';
import type { Dashboard } from './types';

export async function getDashboard(userId: number): Promise<Dashboard> {
  const { data } = await http.get<Dashboard>(`/dashboard/${userId}`);
  return data;
}
