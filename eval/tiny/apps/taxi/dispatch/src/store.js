const crypto = require('crypto');

const rides = new Map();
const drivers = new Map();

function createRide({ riderId, pickup, dropoff }) {
  const ride = {
    id: crypto.randomUUID().slice(0, 8),
    riderId,
    pickup,
    dropoff,
    status: 'searching',
    driverId: null,
    createdAt: new Date().toISOString(),
  };
  rides.set(ride.id, ride);
  return ride;
}

function getRide(id) {
  return rides.get(id);
}

function activeRideForDriver(driverId) {
  for (const ride of rides.values()) {
    if (ride.driverId === driverId && ride.status !== 'completed') return ride;
  }
  return undefined;
}

function upsertDriver(driverId, patch) {
  const current = drivers.get(driverId) || { id: driverId, status: 'offline', position: null };
  const next = { ...current, ...patch };
  drivers.set(driverId, next);
  return next;
}

function getDriver(driverId) {
  return drivers.get(driverId);
}

module.exports = { createRide, getRide, activeRideForDriver, upsertDriver, getDriver };
