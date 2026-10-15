import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { AXIS_MEANINGS, AXIS_VALUES, axisEntries, oneAxisApart } from '../lib/relationship.ts';

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

test('each type has one neighbour per axis that flips only that axis', () => {
  const guide = JSON.parse(
    readFileSync(new URL('../data/relationship-types.json', import.meta.url)),
  );
  for (const type of guide) {
    const near = oneAxisApart(type.axes, guide);
    assert.deepEqual(
      near.map((n) => n.axis),
      ['연애 케미', '연애 온도', '관계 거리', '갈등 해결'],
    );
    near.forEach(({ type: other }, i) => {
      assert.equal(other.axes.filter((v, j) => v !== type.axes[j]).length, 1);
      assert.notEqual(other.axes[i], type.axes[i]);
    });
  }
});

test('every axis value has an everyday meaning', () => {
  assert.deepEqual(Object.keys(AXIS_MEANINGS).sort(), Object.keys(AXIS_VALUES).sort());
});
