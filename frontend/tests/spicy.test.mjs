import assert from 'node:assert/strict';
import test from 'node:test';
import { reachableTitles, spicyCards } from '../lib/spicy.ts';

const spicy = {
  titles: {
    reunion: { id: 'R4', text: '헤어지면 연락처부터 지우는 칼 같은 커플' },
    skinship: { id: 'S3', text: '겉은 얌전, 불 끄면 온도 급상승 커플' },
    jealousy: { id: 'J3', text: '쿨병 걸렸다가 새벽 2시에 폭발하는 커플' },
    temptation: { id: 'C3', text: '한눈팔 시간에 잠이나 자는 귀차니즘 커플' },
  },
  notes: { reunion: 'r', skinship: 's', jealousy: 'j', temptation: 't' },
};

test('spicy cards keep topic order and the wording the link was made with', () => {
  const cards = spicyCards(spicy);
  assert.deepEqual(
    cards.map((c) => c.key),
    ['skinship', 'temptation', 'jealousy', 'reunion'],
  );
  assert.equal(cards[0].title, '겉은 얌전, 불 끄면 온도 급상승 커플');
  assert.equal(cards[0].note, 's');
});

test('type pages list only titles the rules can reach', () => {
  // T03 is independent: the together-only jealousy titles (J1, J2) never apply.
  const jealousy = reachableTitles('T03').find((t) => t.key === 'jealousy');
  assert.ok(!jealousy.titles.includes('읽씹 30초면 부재중 3통 커플'));
  assert.ok(jealousy.titles.length >= 1);
  assert.deepEqual(reachableTitles('T99'), []);
});
