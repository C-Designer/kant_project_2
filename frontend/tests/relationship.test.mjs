import assert from 'node:assert/strict';
import test from 'node:test';
import { axisEntries } from '../lib/relationship.ts';

test('result axes keep their labels even when API property order changes', () => {
  const rows = axisEntries({
    conflict: 'pause',
    distance: 'together',
    temperature: 'steady',
    chemistry: 'complementary',
  });
  assert.deepEqual(
    rows.map(({ label, value }) => [label, value]),
    [
      ['연애 케미', '보완형'],
      ['연애 온도', '안정형'],
      ['관계 거리', '밀착형'],
      ['갈등 해결', '시간 두기'],
    ],
  );
});

test('missing or future axis values do not render as blank or undefined', () => {
  assert.deepEqual(
    axisEntries({ chemistry: 'new-value' }).map((row) => row.value),
    Array(4).fill('확인 필요'),
  );
});
