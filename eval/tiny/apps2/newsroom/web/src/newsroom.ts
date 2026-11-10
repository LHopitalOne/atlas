import { getStory, getSummary, listTopStories, requestSummary } from './generated';
import type { Story, Summary, SummaryJob } from './generated';

export class NewsroomError extends Error {}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function loadFrontPage(limit = 5): Promise<Story[]> {
  const { data, error } = await listTopStories({ query: { limit } });
  if (error || !data) throw new NewsroomError(`front page failed: ${JSON.stringify(error)}`);
  return data;
}

export async function openStory(storyId: number): Promise<Story> {
  const { data, error } = await getStory({ path: { story_id: storyId } });
  if (error || !data) throw new NewsroomError(`story ${storyId} failed: ${JSON.stringify(error)}`);
  return data;
}

export async function askForSummary(storyId: number): Promise<SummaryJob> {
  const { data, error } = await requestSummary({ body: { story_id: storyId } });
  if (error || !data) throw new NewsroomError(`summary request failed: ${JSON.stringify(error)}`);
  return data;
}

export async function waitForSummary(storyId: number, attempts = 30, intervalMs = 500): Promise<Summary> {
  for (let i = 0; i < attempts; i++) {
    const { data } = await getSummary({ path: { story_id: storyId } });
    if (data && data.status === 'ready') return data;
    await sleep(intervalMs);
  }
  throw new NewsroomError(`summary for ${storyId} not ready after ${attempts} attempts`);
}
