const express = require('express');
const store = require('../store');
const hub = require('../realtime/driverHub');

const router = express.Router();

router.post('/', (req, res) => {
  const { riderId, pickup, dropoff } = req.body;
  if (!riderId || !pickup) {
    return res.status(400).json({ error: 'riderId and pickup are required' });
  }
  const ride = store.createRide({ riderId, pickup, dropoff });

  const driverId = hub.availableDriverId();
  if (driverId) {
    hub.notify(driverId, { type: 'ride_offer', ride });
    ride.status = 'offered';
  }
  res.status(201).json(ride);
});

router.get('/:rideId', (req, res) => {
  const ride = store.getRide(req.params.rideId);
  if (!ride) return res.status(404).json({ error: 'not found' });
  res.json(ride);
});

router.post('/:rideId/accept', (req, res) => {
  const ride = store.getRide(req.params.rideId);
  if (!ride) return res.status(404).json({ error: 'not found' });
  if (ride.driverId && ride.driverId !== req.body.driverId) {
    return res.status(409).json({ error: 'ride already taken' });
  }
  ride.driverId = req.body.driverId;
  ride.status = 'accepted';
  store.upsertDriver(ride.driverId, { status: 'busy' });
  res.json(ride);
});

module.exports = router;
