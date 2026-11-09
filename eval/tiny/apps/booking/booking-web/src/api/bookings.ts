import { gql } from "./client";
import {
  AVAILABILITY_QUERY,
  BOOKING_QUERY,
  BOOK_ROOM_MUTATION,
  CANCEL_BOOKING_MUTATION,
  ROOMS_QUERY,
} from "./queries";
import type { Availability, Booking, BookRoomInput, Room } from "./types";

export async function listRooms(city?: string): Promise<Room[]> {
  const data = await gql<{ rooms: Room[] }>(ROOMS_QUERY, { city });
  return data.rooms;
}

export async function checkAvailability(roomId: string, checkIn: string, checkOut: string): Promise<Availability> {
  const data = await gql<{ availability: Availability }>(AVAILABILITY_QUERY, { roomId, checkIn, checkOut });
  return data.availability;
}

export async function getBooking(id: string): Promise<Booking | null> {
  const data = await gql<{ booking: Booking | null }>(BOOKING_QUERY, { id });
  return data.booking;
}

export async function bookRoom(input: BookRoomInput): Promise<Booking> {
  const data = await gql<{ bookRoom: Booking }>(BOOK_ROOM_MUTATION, { input });
  return data.bookRoom;
}

export async function cancelBooking(id: string): Promise<Booking> {
  const data = await gql<{ cancelBooking: Booking }>(CANCEL_BOOKING_MUTATION, { id });
  return data.cancelBooking;
}
