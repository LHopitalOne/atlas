export const config = {
  dispatchUrl: process.env.DISPATCH_URL ?? "http://127.0.0.1:41200",
  driverId: process.env.DRIVER_ID ?? "d-1",
  exitAfterPickup: process.env.EXIT_AFTER_PICKUP === "1",
};

export function streamUrl(): string {
  const url = new URL("/drivers/stream", config.dispatchUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("driverId", config.driverId);
  return url.toString();
}
