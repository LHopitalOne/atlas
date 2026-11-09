const express = require('express');
const store = require('../store');
const hub = require('../realtime/driverHub');

const router = express.Router();

router.post('/:driverId/nearby', (req, res) => {
  const { driverId } = req.params;
  const { lat, lng, cell } = req.body;
  store.upsertDriver(driverId, { position: { lat, lng, cell } });

  const ride = store.activeRideForDriver(driverId);
  if (ride && ride.status === 'accepted') {
    ride.status = 'arriving';
    hub.notify(driverId, { type: 'pickup_nearby', rideId: ride.id, cell });
  }
  res.status(202).json({ driverId, rideId: ride ? ride.id : null });
});

router.get('/:driverId', (req, res) => {
  const driver = store.getDriver(req.params.driverId);
  if (!driver) return res.status(404).json({ error: 'not found' });
  res.json(driver);
});

module.exports = router;
