import { config, streamUrl } from "./config.js";
import { DispatchApi } from "./dispatchApi.js";
import { DriverConnection } from "./connection.js";
import type { ServerMessage } from "./types.js";

const api = new DispatchApi();
const conn = new DriverConnection(streamUrl());

conn.on("ride_offer", async (msg: Extract<ServerMessage, { type: "ride_offer" }>) => {
  console.log(`offer for ride ${msg.ride.id}, accepting`);
  const ride = await api.acceptRide(msg.ride.id, config.driverId);
  console.log(`ride ${ride.id} is ${ride.status}`);
});

conn.on("pickup_nearby", (msg: Extract<ServerMessage, { type: "pickup_nearby" }>) => {
  console.log(`approaching pickup for ride ${msg.rideId} (cell ${msg.cell})`);
  if (config.exitAfterPickup) conn.close();
});

conn.on("close", () => process.exit(0));

await conn.open();
conn.setStatus("available");
console.log(`driver ${config.driverId} online`);

process.on("SIGTERM", () => conn.close());
