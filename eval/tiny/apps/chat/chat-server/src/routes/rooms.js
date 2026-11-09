const express = require('express');
const store = require('../store');
const { postMessage, MessageRejected } = require('../messages');

const router = express.Router();

router.get('/', (req, res) => {
  res.json(store.listRooms());
});

router.post('/', (req, res) => {
  const name = (req.body.name || '').trim();
  if (!name) return res.status(400).json({ error: 'name is required' });
  const { messages, ...room } = store.createRoom(name);
  res.status(201).json(room);
});

router.get('/:roomId/messages', (req, res) => {
  if (!store.getRoom(req.params.roomId)) return res.status(404).json({ error: 'room not found' });
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  res.json(store.history(req.params.roomId, limit));
});

router.post('/:roomId/messages', async (req, res, next) => {
  try {
    const message = await postMessage(req.params.roomId, req.body.author, req.body.text);
    res.status(201).json(message);
  } catch (err) {
    if (err instanceof MessageRejected) return res.status(422).json({ error: err.message });
    next(err);
  }
});

module.exports = router;
