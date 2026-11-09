const BOOKING_FIELDS = `
  fragment BookingFields on Booking {
    id
    roomId
    guestEmail
    checkIn
    checkOut
    status
    totalCents
  }
`;

export const ROOMS_QUERY = `
  query Rooms($city: String) {
    rooms(city: $city) {
      id
      name
      city
      capacity
      nightlyRateCents
    }
  }
`;

export const AVAILABILITY_QUERY = `
  query Availability($roomId: ID!, $checkIn: Date!, $checkOut: Date!) {
    availability(roomId: $roomId, checkIn: $checkIn, checkOut: $checkOut) {
      roomId
      available
      totalCents
    }
  }
`;

export const BOOKING_QUERY = `
  ${BOOKING_FIELDS}
  query GetBooking($id: ID!) {
    booking(id: $id) {
      ...BookingFields
      payment {
        chargeId
        status
        amountCents
        currency
      }
    }
  }
`;

export const BOOK_ROOM_MUTATION = `
  ${BOOKING_FIELDS}
  mutation BookRoom($input: BookRoomInput!) {
    bookRoom(input: $input) {
      ...BookingFields
    }
  }
`;

export const CANCEL_BOOKING_MUTATION = `
  ${BOOKING_FIELDS}
  mutation CancelBooking($id: ID!) {
    cancelBooking(id: $id) {
      ...BookingFields
    }
  }
`;
