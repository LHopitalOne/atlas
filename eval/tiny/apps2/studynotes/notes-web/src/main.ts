import { createNote, deleteNote, listNotes, openNote } from '@/commands/notes';
import { tagCommands } from '@/commands/tags';
import { saveSearch, searchNotes } from '@/lib/search';

// A scripted study session: what a user of the notes UI does in one sitting.
async function studySession() {
  const krebs = await createNote({
    title: 'Krebs cycle',
    body: 'Citric acid cycle oxidises acetyl-CoA, producing NADH and FADH2 for the electron transport chain.',
    remindInMinutes: -5,
  });
  const mitosis = await createNote({
    title: 'Mitosis phases',
    body: 'Prophase, metaphase, anaphase, telophase; the cell cycle ends with cytokinesis.',
  });
  const scratch = await createNote({ title: 'Scratch', body: 'temporary scratch note to delete' });
  console.log(`created ${krebs.id} (${krebs.termCount} terms), ${mitosis.id}, ${scratch.id}`);

  await tagCommands.attach(krebs.id, ['biochem', 'exam-1']);
  await tagCommands.attach(mitosis.id, ['biology']);

  // Fired together on purpose: httpBatchLink folds these into one HTTP request.
  const [notes, tags] = await Promise.all([listNotes(), tagCommands.list()]);
  console.log(`notes=${notes.length} tags=${tags.map((t) => t.name).join(',')}`);

  const opened = await openNote(krebs.id);
  console.log(`opened "${opened.title}" tags=${opened.tags.join(',')}`);

  const results = await searchNotes('cycle');
  console.log(`search "cycle": ${results.map((r) => `${r.note.title}@${r.score}`).join(', ')}`);
  const saved = await saveSearch('cycle');
  console.log(`saved search ${saved.id}`);

  console.log(`deleted scratch: ${await deleteNote(scratch.id)}`);
}

studySession().catch((err) => {
  console.error(err);
  process.exit(1);
});
