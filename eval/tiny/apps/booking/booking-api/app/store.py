import uuid
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RoomRecord:
    id: str
    name: str
    city: str
    capacity: int
    nightly_rate_cents: int


@dataclass
class BookingRecord:
    id: str
    room_id: str
    guest_email: str
    check_in: date
    check_out: date
    total_cents: int
    status: str = "PENDING"
    charge_id: str | None = None

    def overlaps(self, check_in: date, check_out: date) -> bool:
        return self.check_in < check_out and check_in < self.check_out


@dataclass
class BookingStore:
    rooms: dict[str, RoomRecord] = field(default_factory=dict)
    bookings: dict[str, BookingRecord] = field(default_factory=dict)

    @classmethod
    def with_sample_rooms(cls) -> "BookingStore":
        store = cls()
        for room in (
            RoomRecord("r-101", "Harbour View Double", "Lisbon", 2, 12900),
            RoomRecord("r-102", "Alfama Loft", "Lisbon", 3, 15900),
            RoomRecord("r-201", "Canal Studio", "Amsterdam", 2, 17500),
        ):
            store.rooms[room.id] = room
        return store

    def list_rooms(self, city: str | None = None) -> list[RoomRecord]:
        rooms = self.rooms.values()
        if city:
            rooms = [r for r in rooms if r.city.lower() == city.lower()]
        return list(rooms)

    def get_room(self, room_id: str) -> RoomRecord | None:
        return self.rooms.get(room_id)

    def is_available(self, room_id: str, check_in: date, check_out: date) -> bool:
        return not any(
            b.room_id == room_id and b.status != "CANCELLED" and b.overlaps(check_in, check_out)
            for b in self.bookings.values()
        )

    def create_booking(self, room: RoomRecord, guest_email: str, check_in: date, check_out: date) -> BookingRecord:
        nights = (check_out - check_in).days
        booking = BookingRecord(
            id=f"bk_{uuid.uuid4().hex[:10]}",
            room_id=room.id,
            guest_email=guest_email,
            check_in=check_in,
            check_out=check_out,
            total_cents=nights * room.nightly_rate_cents,
        )
        self.bookings[booking.id] = booking
        return booking

    def get_booking(self, booking_id: str) -> BookingRecord | None:
        return self.bookings.get(booking_id)
