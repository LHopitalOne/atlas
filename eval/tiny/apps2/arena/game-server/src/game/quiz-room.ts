import type { Namespace } from 'socket.io';
import { config } from '../config.js';
import { QuizEvents, type QuestionPayload, type RoundResultPayload } from '../events.js';
import type { ScoreReporter } from '../scoring/udp-reporter.js';
import type { Question } from './question-bank.js';

type RoomState = 'waiting' | 'playing' | 'finished';

export class QuizRoom {
  private readonly players = new Map<string, string>();
  private readonly totals = new Map<string, number>();
  private answers = new Map<string, string>();
  private current: Question | null = null;
  private allAnswered: (() => void) | null = null;
  private state: RoomState = 'waiting';

  constructor(
    readonly id: string,
    private readonly nsp: Namespace,
    private readonly reporter: ScoreReporter,
  ) {}

  get isWaiting(): boolean {
    return this.state === 'waiting';
  }

  get playerCount(): number {
    return this.players.size;
  }

  addPlayer(socketId: string, name: string): void {
    this.players.set(socketId, name);
    this.totals.set(name, this.totals.get(name) ?? 0);
  }

  removePlayer(socketId: string): void {
    this.players.delete(socketId);
  }

  recordAnswer(socketId: string, questionId: string, choice: string): void {
    if (!this.current || this.current.id !== questionId || !this.players.has(socketId)) return;
    this.answers.set(socketId, choice);
    if (this.answers.size >= this.players.size) this.allAnswered?.();
  }

  async play(questions: Question[]): Promise<void> {
    this.state = 'playing';
    for (const [index, question] of questions.entries()) {
      await this.playRound(question, index + 1, questions.length);
    }
    this.state = 'finished';
  }

  private async playRound(question: Question, round: number, totalRounds: number): Promise<void> {
    this.current = question;
    this.answers = new Map();
    this.askQuestion({
      questionId: question.id,
      round,
      totalRounds,
      category: question.category,
      text: question.text,
      choices: question.choices,
    });
    await this.waitForAnswers();

    const roundScores: Record<string, number> = {};
    for (const [socketId, name] of this.players) {
      const points = this.answers.get(socketId) === question.correct ? config.game.pointsPerCorrect : 0;
      roundScores[name] = points;
      this.totals.set(name, (this.totals.get(name) ?? 0) + points);
    }
    this.reporter.report({ room: this.id, round, scores: roundScores });
    this.announceResult({
      round,
      correct: question.correct,
      scores: Object.fromEntries(this.totals),
      final: round === totalRounds,
    });
  }

  private waitForAnswers(): Promise<void> {
    return new Promise((resolve) => {
      const timer = setTimeout(done, config.game.roundTimeoutMs);
      const self = this;
      function done(): void {
        clearTimeout(timer);
        self.allAnswered = null;
        resolve();
      }
      this.allAnswered = done;
    });
  }

  private askQuestion(payload: QuestionPayload): void {
    this.broadcast(QuizEvents.QUESTION, payload);
  }

  private announceResult(payload: RoundResultPayload): void {
    this.broadcast(QuizEvents.ROUND_RESULT, payload);
  }

  private broadcast(event: string, payload: QuestionPayload | RoundResultPayload): void {
    this.nsp.to(this.id).emit(event, payload);
  }
}
