import { Router } from 'express';
import type { ScorekeeperClient } from '../clients/scorekeeper.js';
import { traceRecv } from '../trace.js';

export function leaderboardRouter(scorekeeper: ScorekeeperClient): Router {
  const router = Router();

  router.get('/leaderboard', async (_req, res, next) => {
    traceRecv('GET /api/leaderboard');
    try {
      const scores = await scorekeeper.fetchScores();
      scores.sort((a, b) => b.points - a.points);
      res.json({ leaderboard: scores });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
