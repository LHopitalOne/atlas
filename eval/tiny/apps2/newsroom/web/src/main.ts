import { configureApi } from './api';
import { askForSummary, loadFrontPage, openStory, waitForSummary } from './newsroom';
import type { Story } from './generated';

const apiMeta = document.querySelector<HTMLMetaElement>('meta[name="newsroom-api"]');
configureApi(apiMeta?.content);

const list = document.querySelector<HTMLOListElement>('#stories')!;
const detail = document.querySelector<HTMLElement>('#detail')!;

function storyItem(story: Story): HTMLLIElement {
  const li = document.createElement('li');
  const title = document.createElement('button');
  title.textContent = `${story.title} (${story.score})`;
  title.addEventListener('click', () => void showStory(story.id));
  li.append(title);
  return li;
}

async function showStory(id: number): Promise<void> {
  const story = await openStory(id);
  detail.innerHTML = '';
  const heading = document.createElement('h2');
  heading.textContent = story.title;
  const summarize = document.createElement('button');
  summarize.textContent = 'Summarise discussion';
  const output = document.createElement('p');
  summarize.addEventListener('click', async () => {
    output.textContent = 'Summarising...';
    await askForSummary(story.id);
    output.textContent = (await waitForSummary(story.id)).summary ?? '';
  });
  detail.append(heading, summarize, output);
}

loadFrontPage(15).then((stories) => list.replaceChildren(...stories.map(storyItem)));
