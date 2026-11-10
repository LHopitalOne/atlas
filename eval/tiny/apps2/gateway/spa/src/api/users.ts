import { http } from './client';
import type { User, WishlistItem } from './types';

export async function listUsers(): Promise<User[]> {
  const { data } = await http.get<User[]>('/users');
  return data;
}

export async function getUser(id: number): Promise<User> {
  const { data } = await http.get<User>(`/users/${id}`);
  return data;
}

export async function registerUser(name: string, email: string): Promise<User> {
  const { data } = await http.post<User>('/users', { name, email });
  return data;
}

export async function getWishlist(userId: number): Promise<WishlistItem[]> {
  const { data } = await http.get<WishlistItem[]>(`/users/${userId}/wishlist`);
  return data;
}
