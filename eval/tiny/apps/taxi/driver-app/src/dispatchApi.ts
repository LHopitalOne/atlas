import { config } from "./config.js";
import type { Ride } from "./types.js";

export class DispatchApi {
  constructor(private readonly baseUrl: string = config.dispatchUrl) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`${method} ${path} failed: ${res.status}`);
    }
    return (await res.json()) as T;
  }

  acceptRide(rideId: string, driverId: string): Promise<Ride> {
    return this.request<Ride>("POST", `/rides/${encodeURIComponent(rideId)}/accept`, { driverId });
  }
}
