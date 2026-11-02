import { test } from 'node:test';
import assert from 'node:assert/strict';

test('an invalid browser language tag does not stop the app from starting', async () => {
  const desc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US@posix'] }, configurable: true });
  try {
    const { fmt } = await import('../src/util/format.js?posix');
    assert.equal(fmt(1234567), '1,234,567');
  } finally {
    if (desc) Object.defineProperty(globalThis, 'navigator', desc);
  }
});
