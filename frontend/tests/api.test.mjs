import assert from 'node:assert/strict';
import test from 'node:test';
import { withErrorNumber } from '../lib/api.ts';

test('server errors show the searchable tail of the request id', () => {
  const message = '분석을 마치지 못했어요. 잠시 후 다시 시도해 주세요.';
  assert.equal(
    withErrorNumber(message, 'icn1::abc12-1700000000000-deadbeef'),
    message + ' (오류 번호 deadbeef)',
  );
  assert.equal(withErrorNumber(message, '0f3c9a'), message + ' (오류 번호 0f3c9a)');
  assert.equal(withErrorNumber(message, undefined), message);
});
