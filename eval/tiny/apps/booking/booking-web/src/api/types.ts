export interface Room {
  id: string;
  name: string;
  city: string;
  capacity: number;
  nightlyRateCents: number;
}

export interface Availability {
  roomId: string;
  available: boolean;
  totalCents: number;
}

export interface Payment {
  chargeId: string;
  status: string;
  amountCents: number;
  currency: string;
}

export interface Booking {
  id: string;
  roomId: string;
  guestEmail: string;
  checkIn: string;
  checkOut: string;
  status: string;
  totalCents: number;
  payment?: Payment | null;
}

export interface BookRoomInput {
  roomId: string;
  guestEmail: string;
  checkIn: string;
  checkOut: string;
}
