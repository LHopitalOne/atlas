import { promises as fs } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';

const dataFile = path.resolve(process.env.NOTES_DATA_FILE || './data/notes.json');

async function readAll() {
  try {
    return JSON.parse(await fs.readFile(dataFile, 'utf8'));
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }
}

async function writeAll(notes) {
  await fs.mkdir(path.dirname(dataFile), { recursive: true });
  await fs.writeFile(dataFile, JSON.stringify(notes, null, 2));
}

export async function listNotes() {
  const notes = await readAll();
  return notes.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function getNote(id) {
  const notes = await readAll();
  return notes.find((n) => n.id === id) || null;
}

export async function createNote({ title, body = '' }) {
  const notes = await readAll();
  const now = new Date().toISOString();
  const note = { id: randomUUID(), title, body, createdAt: now, updatedAt: now };
  notes.push(note);
  await writeAll(notes);
  return note;
}

export async function updateNote(id, changes) {
  const notes = await readAll();
  const idx = notes.findIndex((n) => n.id === id);
  if (idx === -1) return null;
  const note = {
    ...notes[idx],
    title: changes.title ?? notes[idx].title,
    body: changes.body ?? notes[idx].body,
    updatedAt: new Date().toISOString(),
  };
  notes[idx] = note;
  await writeAll(notes);
  return note;
}

export async function deleteNote(id) {
  const notes = await readAll();
  const remaining = notes.filter((n) => n.id !== id);
  if (remaining.length === notes.length) return false;
  await writeAll(remaining);
  return true;
}
