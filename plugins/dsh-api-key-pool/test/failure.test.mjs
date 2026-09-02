import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decideFailureAction, nextCooldownMs, FAILURE_ACTIONS } from '../src/failure.js';

test('分类表全覆盖：每个已知 code 映射到预期动作', () => {
  const expected = {
    AUTH: 'cooldown',
    RATE_LIMIT: 'cooldown',
    QUOTA: 'cooldown',
    INVALID_CREDENTIAL: 'disable',
    TIMEOUT: 'count',
    TRANSPORT: 'count',
    SERVER: 'count',
    EMPTY_RESPONSE: 'count',
  };
  for (const [code, action] of Object.entries(expected)) {
    assert.equal(decideFailureAction(code).action, action, code);
  }
  assert.equal(Object.keys(FAILURE_ACTIONS).length, 8);
});

test('请求侧失败透传（ignore），未知/空 code 也透传', () => {
  for (const code of ['INVALID_REQUEST', 'CONTEXT_WINDOW_EXCEEDED', 'MISSING_CREDENTIAL', 'ABORTED']) {
    assert.equal(decideFailureAction(code).action, 'ignore', code);
  }
  assert.equal(decideFailureAction('SOMETHING_NEW').action, 'ignore');
  assert.equal(decideFailureAction('').action, 'ignore');
  assert.equal(decideFailureAction(undefined).action, 'ignore');
});

test('决策附带的抬升/长冷却标记', () => {
  assert.deepEqual(decideFailureAction('RATE_LIMIT'), { action: 'cooldown', useRetryAfter: true, longCooldown: false });
  assert.deepEqual(decideFailureAction('QUOTA'), { action: 'cooldown', useRetryAfter: false, longCooldown: true });
  assert.deepEqual(decideFailureAction('AUTH'), { action: 'cooldown', useRetryAfter: false, longCooldown: false });
});

test('指数退避：failureCount 递增翻倍，封顶 maxCooldownMs', () => {
  const args = { cooldownMs: 1000, maxCooldownMs: 8000 };
  assert.equal(nextCooldownMs({ ...args, failureCount: 1 }), 1000);
  assert.equal(nextCooldownMs({ ...args, failureCount: 2 }), 2000);
  assert.equal(nextCooldownMs({ ...args, failureCount: 3 }), 4000);
  assert.equal(nextCooldownMs({ ...args, failureCount: 4 }), 8000);
  assert.equal(nextCooldownMs({ ...args, failureCount: 10 }), 8000);
});

test('RATE_LIMIT：Retry-After 抬升冷却', () => {
  const ms = nextCooldownMs({
    failureCount: 1, cooldownMs: 1000, maxCooldownMs: 8000, retryAfterMs: 5000, useRetryAfter: true,
  });
  assert.equal(ms, 5000);
  // Retry-After 小于退避值时取退避值
  const ms2 = nextCooldownMs({
    failureCount: 2, cooldownMs: 1000, maxCooldownMs: 8000, retryAfterMs: 500, useRetryAfter: true,
  });
  assert.equal(ms2, 2000);
});

test('QUOTA：直接进入冷却上限', () => {
  const ms = nextCooldownMs({ failureCount: 1, cooldownMs: 1000, maxCooldownMs: 60000, longCooldown: true });
  assert.equal(ms, 60000);
});

test('非法输入回退安全默认', () => {
  assert.equal(nextCooldownMs({ failureCount: 0, cooldownMs: 1000, maxCooldownMs: 8000 }), 1000);
  assert.equal(nextCooldownMs({ failureCount: -3, cooldownMs: 1000, maxCooldownMs: 8000 }), 1000);
  assert.equal(nextCooldownMs({ failureCount: 1, cooldownMs: NaN, maxCooldownMs: NaN }), 30000);
});
