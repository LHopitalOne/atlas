import { bookRoom, cancelBooking, checkAvailability, getBooking, listRooms } from "../src/api/bookings";

async function main(): Promise<void> {
  const rooms = await listRooms("Lisbon");
  console.log(`rooms in Lisbon: ${rooms.map((r) => r.id).join(", ")}`);

  const room = rooms[0];
  const availability = await checkAvailability(room.id, "2026-12-01", "2026-12-04");
  console.log(`available: ${availability.available} total: ${availability.totalCents}`);

  const booking = await bookRoom({
    roomId: room.id,
    guestEmail: "ana@example.com",
    checkIn: "2026-12-01",
    checkOut: "2026-12-04",
  });
  console.log(`booked ${booking.id} -> ${booking.status}`);

  const fetched = await getBooking(booking.id);
  console.log(`payment ${fetched?.payment?.chargeId} -> ${fetched?.payment?.status}`);

  const cancelled = await cancelBooking(booking.id);
  console.log(`cancelled ${cancelled.id} -> ${cancelled.status}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
