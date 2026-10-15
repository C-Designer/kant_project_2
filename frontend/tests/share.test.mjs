import assert from 'node:assert/strict';
import test from 'node:test';
import { codeFromHash, formatDate, shareUrl } from '../lib/share.ts';

const code = 'q1Z' + 'Kx-_'.repeat(150) + '.' + 'A'.repeat(21) + 'g';

test('share links keep the signed code in the fragment', () => {
  assert.equal(
    shareUrl('https://kant-lovecode.vercel.app', code),
    'https://kant-lovecode.vercel.app/r#' + code,
  );
});

test('only well-formed codes are read from the hash', () => {
  assert.equal(codeFromHash('#' + code), code);
  for (const bad of ['', '#', '#abc', '#' + code + 'x', '#' + code.replace('.', ''), '#a.b']) {
    assert.equal(codeFromHash(bad), null, bad);
  }
});

test('the body length limit matches MAX_BODY_CHARS in backend/lovecode/share.py', () => {
  const sig = '.' + 'A'.repeat(21) + 'g';
  assert.ok(codeFromHash('#' + 'a'.repeat(4000) + sig));
  assert.equal(codeFromHash('#' + 'a'.repeat(4001) + sig), null);
});

test('dates render in Korea time and stay empty when invalid', () => {
  assert.match(formatDate('2026-10-15T16:00:00+00:00'), /2026년 10월 16일/);
  assert.equal(formatDate('not a date'), '');
});
