import { io, type Socket } from 'socket.io-client';
import {
  QUIZ_NAMESPACE,
  QuizEvents,
  type LeaderboardEntry,
  type QuestionPayload,
  type RoundResultPayload,
} from './protocol.js';

type Handler<T> = (payload: T) => void;

/** Thin wrapper over the /quiz namespace socket plus the leaderboard REST call. */
export class QuizClient {
  private readonly socket: Socket;

  constructor(private readonly serverUrl: string) {
    this.socket = io(`${serverUrl}${QUIZ_NAMESPACE}`, {
      transports: ['websocket'],
      auth: { client: 'player-web' },
      autoConnect: false,
    });
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.socket.once('connect', () => resolve());
      this.socket.once('connect_error', reject);
      this.socket.connect();
    });
  }

  disconnect(): void {
    this.socket.disconnect();
  }

  join(room: string, name: string): void {
    this.send(QuizEvents.JOIN, { room, name });
  }

  answer(questionId: string, choice: string): void {
    this.send(QuizEvents.ANSWER, { questionId, choice });
  }

  onQuestion(handler: Handler<QuestionPayload>): void {
    this.socket.on(QuizEvents.QUESTION, handler);
  }

  onRoundResult(handler: Handler<RoundResultPayload>): void {
    this.socket.on(QuizEvents.ROUND_RESULT, handler);
  }

  async fetchLeaderboard(): Promise<LeaderboardEntry[]> {
    const res = await fetch(new URL('/api/leaderboard', this.serverUrl));
    if (!res.ok) throw new Error(`leaderboard request failed: ${res.status}`);
    const body = (await res.json()) as { leaderboard: LeaderboardEntry[] };
    return body.leaderboard;
  }

  private send(event: string, payload: object): void {
    this.socket.emit(event, payload);
  }
}
