import { QuizClient } from './quiz-client.js';

const serverUrl =
  document.querySelector<HTMLMetaElement>('meta[name="arena-server"]')?.content ?? window.location.origin;
const client = new QuizClient(serverUrl);

const form = document.querySelector<HTMLFormElement>('#join-form')!;
const questionBox = document.querySelector<HTMLElement>('#question')!;
const meta = document.querySelector<HTMLElement>('#question-meta')!;
const text = document.querySelector<HTMLElement>('#question-text')!;
const choices = document.querySelector<HTMLElement>('#choices')!;
const scores = document.querySelector<HTMLOListElement>('#scores')!;

async function renderLeaderboard(): Promise<void> {
  const entries = await client.fetchLeaderboard();
  scores.replaceChildren(
    ...entries.map((entry) => {
      const li = document.createElement('li');
      li.textContent = `${entry.player}: ${entry.points}`;
      return li;
    }),
  );
}

client.onQuestion((q) => {
  questionBox.hidden = false;
  meta.textContent = `Round ${q.round}/${q.totalRounds} - ${q.category}`;
  text.innerHTML = q.text;
  choices.replaceChildren(
    ...q.choices.map((choice) => {
      const button = document.createElement('button');
      button.innerHTML = choice;
      button.addEventListener('click', () => client.answer(q.questionId, choice), { once: true });
      return button;
    }),
  );
});

client.onRoundResult((result) => {
  if (result.final) {
    questionBox.hidden = true;
    void renderLeaderboard();
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  await client.connect();
  client.join(String(data.get('room')), String(data.get('name')));
  form.hidden = true;
});
