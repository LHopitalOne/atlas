const express = require('express');
const moderation = require('../moderationClient');

const router = express.Router();

router.post('/', async (req, res, next) => {
  const { reporter, reported, roomId, reason } = req.body;
  if (!reporter || !reported) return res.status(400).json({ error: 'reporter and reported are required' });
  try {
    const result = await moderation.reportUser({ reporter, reported, roomId, reason });
    res.status(202).json({ ticketId: result.ticketId, openReports: result.openReports });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
