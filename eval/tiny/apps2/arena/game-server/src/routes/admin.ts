import { Router } from 'express';
import type { QuestionBank, QuestionInput } from '../game/question-bank.js';
import { traceRecv } from '../trace.js';

export function adminRouter(bank: QuestionBank): Router {
  const router = Router();

  router.post('/questions', (req, res) => {
    const items = (req.body?.questions ?? []) as QuestionInput[];
    traceRecv('POST /admin/questions', `count=${items.length}`);
    const total = bank.add(items);
    res.status(201).json({ added: items.length, total });
  });

  return router;
}
