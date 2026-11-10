// Copy of game-server/src/events.ts (the wire protocol).
export const QUIZ_NAMESPACE = '/quiz';

export const QuizEvents = {
  JOIN: 'join',
  ANSWER: 'answer',
  QUESTION: 'question',
  ROUND_RESULT: 'round_result',
} as const;

export interface QuestionPayload {
  questionId: string;
  round: number;
  totalRounds: number;
  category: string;
  text: string;
  choices: string[];
}

export interface RoundResultPayload {
  round: number;
  correct: string;
  scores: Record<string, number>;
  final: boolean;
}

export interface LeaderboardEntry {
  player: string;
  points: number;
}
