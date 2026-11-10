import { randomUUID } from 'node:crypto';

export interface Question {
  id: string;
  category: string;
  text: string;
  correct: string;
  choices: string[];
}

export interface QuestionInput {
  category: string;
  question: string;
  correct_answer: string;
  incorrect_answers: string[];
}

function shuffle<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

export class QuestionBank {
  private readonly questions: Question[] = [];

  add(inputs: QuestionInput[]): number {
    for (const input of inputs) {
      this.questions.push({
        id: randomUUID(),
        category: input.category,
        text: input.question,
        correct: input.correct_answer,
        choices: shuffle([input.correct_answer, ...input.incorrect_answers]),
      });
    }
    return this.questions.length;
  }

  get size(): number {
    return this.questions.length;
  }

  snapshot(): Question[] {
    return [...this.questions];
  }
}
