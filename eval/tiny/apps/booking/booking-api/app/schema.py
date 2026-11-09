from datetime import date

import strawberry
from strawberry.fastapi import BaseContext
from strawberry.types import Info

from .graphql_logging import OperationLogger
from .payments import PaymentsClient
from .settings import get_settings
from .store import BookingRecord, BookingStore, RoomRecord


class GraphQLContext(BaseContext):
    def __init__(self, store: BookingStore, payments: PaymentsClient) -> None:
        super().__init__()
        self.store = store
        self.payments = payments


AppInfo = Info[GraphQLContext, None]


@strawberry.type
class Room:
    id: strawberry.ID
    name: str
    city: str
    capacity: int
    nightly_rate_cents: int

    @classmethod
    def from_record(cls, record: RoomRecord) -> "Room":
        return cls(
            id=strawberry.ID(record.id),
            name=record.name,
            city=record.city,
            capacity=record.capacity,
            nightly_rate_cents=record.nightly_rate_cents,
        )


@strawberry.type
class Availability:
    room_id: strawberry.ID
    check_in: date
    check_out: date
    available: bool
    total_cents: int


@strawberry.type
class Payment:
    charge_id: str
    status: str
    amount_cents: int
    currency: str


@strawberry.type
class Booking:
    id: strawberry.ID
    room_id: strawberry.ID
    guest_email: str
    check_in: date
    check_out: date
    status: str
    total_cents: int
    charge_id: strawberry.Private[str | None]

    @classmethod
    def from_record(cls, record: BookingRecord) -> "Booking":
        return cls(
            id=strawberry.ID(record.id),
            room_id=strawberry.ID(record.room_id),
            guest_email=record.guest_email,
            check_in=record.check_in,
            check_out=record.check_out,
            status=record.status,
            total_cents=record.total_cents,
            charge_id=record.charge_id,
        )

    @strawberry.field
    async def payment(self, info: AppInfo) -> Payment | None:
        if self.charge_id is None:
            return None
        charge = await info.context.payments.get_charge(self.charge_id)
        return Payment(
            charge_id=charge.id,
            status=charge.status,
            amount_cents=charge.amount_cents,
            currency=charge.currency,
        )


@strawberry.input
class BookRoomInput:
    room_id: strawberry.ID
    guest_email: str
    check_in: date
    check_out: date


def _nights(check_in: date, check_out: date) -> int:
    nights = (check_out - check_in).days
    if nights <= 0:
        raise ValueError("check_out must be after check_in")
    return nights


@strawberry.type
class Query:
    @strawberry.field
    def rooms(self, info: AppInfo, city: str | None = None) -> list[Room]:
        return [Room.from_record(r) for r in info.context.store.list_rooms(city)]

    @strawberry.field
    def availability(self, info: AppInfo, room_id: strawberry.ID, check_in: date, check_out: date) -> Availability:
        store = info.context.store
        room = store.get_room(room_id)
        if room is None:
            raise ValueError(f"unknown room {room_id}")
        return Availability(
            room_id=room_id,
            check_in=check_in,
            check_out=check_out,
            available=store.is_available(room_id, check_in, check_out),
            total_cents=_nights(check_in, check_out) * room.nightly_rate_cents,
        )

    @strawberry.field
    def booking(self, info: AppInfo, id: strawberry.ID) -> Booking | None:
        record = info.context.store.get_booking(id)
        return Booking.from_record(record) if record else None


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def book_room(self, info: AppInfo, input: BookRoomInput) -> Booking:
        store = info.context.store
        room = store.get_room(input.room_id)
        if room is None:
            raise ValueError(f"unknown room {input.room_id}")
        _nights(input.check_in, input.check_out)
        if not store.is_available(room.id, input.check_in, input.check_out):
            raise ValueError("room is not available for these dates")

        record = store.create_booking(room, input.guest_email, input.check_in, input.check_out)
        charge = await info.context.payments.charge(
            booking_id=record.id,
            amount_cents=record.total_cents,
            currency=get_settings().currency,
            customer_email=record.guest_email,
        )
        record.charge_id = charge.id
        record.status = "CONFIRMED" if charge.status == "succeeded" else "PAYMENT_FAILED"
        return Booking.from_record(record)

    @strawberry.mutation
    async def cancel_booking(self, info: AppInfo, id: strawberry.ID) -> Booking:
        record = info.context.store.get_booking(id)
        if record is None:
            raise ValueError(f"unknown booking {id}")
        if record.charge_id and record.status == "CONFIRMED":
            await info.context.payments.refund(record.charge_id)
        record.status = "CANCELLED"
        return Booking.from_record(record)


schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[OperationLogger])
