export interface Ride {
  id: string;
  riderId: string;
  pickup: { lat: number; lng: number };
  dropoff?: { lat: number; lng: number };
  status: string;
  driverId: string | null;
}

export type ServerMessage =
  | { type: "ride_offer"; ride: Ride }
  | { type: "pickup_nearby"; rideId: string; cell: string };
