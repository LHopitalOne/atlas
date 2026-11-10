// Wire protocol shared (by copy) with player-web and quiz-bot.
export const QUIZ_NAMESPACE = '/quiz';

export const QuizEvents = {
  JOIN: 'join',
  ANSWER: 'answer',
  QUESTION: 'question',
  ROUND_RESULT: 'round_result',
} as const;

export type QuizEventName = (typeof QuizEvents)[keyof typeof QuizEvents];

export interface JoinPayload {
  room: string;
  name: string;
}

export interface AnswerPayload {
  questionId: string;
  choice: string;
}

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
