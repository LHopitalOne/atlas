// Headless player: drives the same QuizClient the browser uses.
import { QuizClient } from '../src/quiz-client.js';

const serverUrl = process.env.GAME_SERVER_URL ?? 'http://127.0.0.1:44010';
const room = process.env.ROOM ?? 'arena-1';
const name = process.env.PLAYER_NAME ?? 'alice';

const client = new QuizClient(serverUrl);

const finished = new Promise<void>((resolve) => {
  client.onQuestion((q) => {
    console.log(`RECV A03 player-web question round=${q.round}/${q.totalRounds}`);
    client.answer(q.questionId, q.choices[0]);
  });
  client.onRoundResult((result) => {
    console.log(`RECV A04 player-web round_result round=${result.round} final=${result.final}`);
    if (result.final) resolve();
  });
});

await client.connect();
client.join(room, name);
await finished;

const leaderboard = await client.fetchLeaderboard();
console.log(`leaderboard: ${leaderboard.map((e) => `${e.player}=${e.points}`).join(', ')}`);
client.disconnect();
