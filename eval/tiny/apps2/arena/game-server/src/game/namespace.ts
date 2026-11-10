import type { Server, Socket } from 'socket.io';
import { config } from '../config.js';
import { QUIZ_NAMESPACE, QuizEvents, type AnswerPayload, type JoinPayload } from '../events.js';
import type { ScoreReporter } from '../scoring/udp-reporter.js';
import { traceRecv } from '../trace.js';
import type { QuestionBank } from './question-bank.js';
import { QuizRoom } from './quiz-room.js';

interface SocketData {
  client: string;
  room?: QuizRoom;
}

export function registerQuizNamespace(io: Server, bank: QuestionBank, reporter: ScoreReporter): void {
  const quiz = io.of(QUIZ_NAMESPACE);
  const rooms = new Map<string, QuizRoom>();

  function roomFor(id: string): QuizRoom {
    let room = rooms.get(id);
    if (!room) {
      room = new QuizRoom(id, quiz, reporter);
      rooms.set(id, room);
    }
    return room;
  }

  function maybeStart(room: QuizRoom): void {
    if (!room.isWaiting || room.playerCount < config.game.minPlayers || bank.size === 0) return;
    console.log(`room ${room.id}: starting with ${room.playerCount} players, ${bank.size} questions`);
    void room.play(bank.snapshot()).then(() => console.log(`room ${room.id}: finished`));
  }

  quiz.on('connection', (socket: Socket) => {
    const data = socket.data as SocketData;
    data.client = String(socket.handshake.auth?.client ?? 'unknown');

    socket.on(QuizEvents.JOIN, async (payload: JoinPayload) => {
      traceRecv(`join:${data.client}`, `room=${payload.room} name=${payload.name}`);
      const room = roomFor(payload.room);
      await socket.join(room.id);
      room.addPlayer(socket.id, payload.name);
      data.room = room;
      maybeStart(room);
    });

    socket.on(QuizEvents.ANSWER, (payload: AnswerPayload) => {
      traceRecv(`answer:${data.client}`, `question=${payload.questionId}`);
      data.room?.recordAnswer(socket.id, payload.questionId, payload.choice);
    });

    socket.on('disconnect', () => {
      data.room?.removePlayer(socket.id);
    });
  });
}
