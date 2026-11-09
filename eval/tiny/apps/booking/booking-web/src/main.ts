import { bookRoom, checkAvailability, listRooms } from "./api/bookings";
import type { Room } from "./api/types";
import { formatPrice } from "./format";

const root = document.querySelector<HTMLElement>("#app")!;

function roomCard(room: Room): HTMLElement {
  const card = document.createElement("article");
  card.innerHTML = `
    <h2>${room.name}</h2>
    <p>${room.city} &middot; sleeps ${room.capacity} &middot; ${formatPrice(room.nightlyRateCents)} / night</p>
    <form>
      <input name="email" type="email" placeholder="you@example.com" required />
      <input name="checkIn" type="date" required />
      <input name="checkOut" type="date" required />
      <button type="submit">Book</button>
      <output></output>
    </form>
  `;
  const form = card.querySelector("form")!;
  const output = card.querySelector("output")!;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(form);
    const checkIn = String(values.get("checkIn"));
    const checkOut = String(values.get("checkOut"));
    try {
      const availability = await checkAvailability(room.id, checkIn, checkOut);
      if (!availability.available) {
        output.textContent = "Sorry, those dates are taken.";
        return;
      }
      const booking = await bookRoom({ roomId: room.id, guestEmail: String(values.get("email")), checkIn, checkOut });
      output.textContent = `Booked! ${booking.id} (${booking.status}) ${formatPrice(booking.totalCents)}`;
    } catch (err) {
      output.textContent = err instanceof Error ? err.message : "Something went wrong";
    }
  });
  return card;
}

async function render(): Promise<void> {
  root.textContent = "Loading rooms...";
  const rooms = await listRooms();
  root.replaceChildren(...rooms.map(roomCard));
}

render().catch((err) => {
  root.textContent = `Could not load rooms: ${err}`;
});
