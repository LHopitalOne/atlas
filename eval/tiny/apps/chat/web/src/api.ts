import { API_URL } from './config.js';
import type { Message, ReportTicket, Room } from './types.js';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export class ChatApi {
  constructor(private baseUrl: string = API_URL) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data.error ?? res.statusText);
    return data as T;
  }

  listRooms(): Promise<Room[]> {
    return this.request('GET', '/api/rooms');
  }

  createRoom(name: string): Promise<Room> {
    return this.request('POST', '/api/rooms', { name });
  }

  getHistory(roomId: string, limit = 50): Promise<Message[]> {
    return this.request('GET', `/api/rooms/${encodeURIComponent(roomId)}/messages?limit=${limit}`);
  }

  postMessage(roomId: string, author: string, text: string): Promise<Message> {
    return this.request('POST', `/api/rooms/${encodeURIComponent(roomId)}/messages`, { author, text });
  }

  reportUser(reporter: string, reported: string, roomId: string, reason: string): Promise<ReportTicket> {
    return this.request('POST', '/api/reports', { reporter, reported, roomId, reason });
  }
}

export function avatarUrl(user: string): string {
  return `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(user)}`;
}
