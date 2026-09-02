import { test } from 'node:test';
import assert from 'node:assert/strict';
import { KeyPoolRuntime, POOL_EXHAUSTED_CODE } from '../src/pools.js';
import { validatePoolConfig } from '../src/schema.js';

const KEY_A = 'k-00000000-0000-4000-8000-00000000000a';
const KEY_B = 'k-00000000-0000-4000-8000-00000000000b';
const KEY_C = 'k-00000000-0000-4000-8000-00000000000c';

function makeConfig(overrides = {}) {
  return validatePoolConfig({
    pools: {
      demo: {
        api: 'openai-completions',
        baseURL: 'https://api.example.com/v1',
        models: [{ id: 'model-a' }],
        keyIds: [KEY_A, KEY_B, KEY_C],
        cooldownMs: 1000,
        maxCooldownMs: 30000,
        ...overrides,
      },
    },
  });
}

function makeRuntime({ values = {}, config = makeConfig(), t = 0 } = {}) {
  const now = { value: t };
  const runtime = new KeyPoolRuntime({
    config,
    resolveKey: async (keyId) => values[keyId],
    now: () => now.value,
  });
  return { runtime, clock: now };
}

const VALUES = { [KEY_A]: 'sk-aaa', [KEY_B]: 'sk-bbb', [KEY_C]: 'sk-ccc' };

test('round-robin：三 Key 顺序循环分布', async () => {
  const { runtime } = makeRuntime({ values: VALUES });
  const picks = [];
  for (let i = 0; i < 6; i += 1) {
    picks.push(await runtime.beginStream('pool-demo'));
  }
  assert.deepEqual(picks.map((p) => p.keyId), [KEY_A, KEY_B, KEY_C, KEY_A, KEY_B, KEY_C]);
  assert.deepEqual(picks.map((p) => p.value), ['sk-aaa', 'sk-bbb', 'sk-ccc', 'sk-aaa', 'sk-bbb', 'sk-ccc']);
  assert.equal(picks[0].route, 'pool-demo');
  assert.equal(picks[0].poolId, 'demo');
});

test('冷却中的 Key 被跳过，其余继续轮询', async () => {
  const { runtime, clock } = makeRuntime({ values: VALUES });
  await runtime.beginStream('pool-demo'); // KEY_A，游标 0
  runtime.recordFailure('pool-demo', KEY_A, 'AUTH'); // KEY_A 冷却 1000ms
  const second = await runtime.beginStream('pool-demo'); // KEY_B
  assert.equal(second.keyId, KEY_B);
  const third = await runtime.beginStream('pool-demo'); // KEY_C（跳过冷却中的 KEY_A）
  assert.equal(third.keyId, KEY_C);
  clock.value = 1000; // 冷却到期
  const fourth = await runtime.beginStream('pool-demo'); // 回到 KEY_A
  assert.equal(fourth.keyId, KEY_A);
});

test('全部 Key 冷却 → POOL_EXHAUSTED；到期后恢复', async () => {
  const { runtime, clock } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_A, 'AUTH');
  runtime.recordFailure('pool-demo', KEY_B, 'AUTH');
  runtime.recordFailure('pool-demo', KEY_C, 'AUTH');
  await assert.rejects(() => runtime.beginStream('pool-demo'), (err) => {
    assert.equal(err.code, POOL_EXHAUSTED_CODE);
    assert.match(err.message, /暂无可用 Key/);
    return true;
  });
  clock.value = 1000;
  const pick = await runtime.beginStream('pool-demo');
  assert.ok([KEY_A, KEY_B, KEY_C].includes(pick.keyId));
});

test('未知 route → POOL_EXHAUSTED', async () => {
  const { runtime } = makeRuntime({ values: VALUES });
  await assert.rejects(() => runtime.beginStream('pool-other'), (err) => err.code === POOL_EXHAUSTED_CODE);
});

test('失败分类：AUTH 指数冷却，成功后清零', async () => {
  const { runtime, clock } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_A, 'AUTH'); // failureCount=1 → 1000ms
  let snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).state, 'cooling');
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).cooldownRemainingMs, 1000);

  clock.value = 1000; // 第一次冷却到期，Key 恢复可选
  const pick = await runtime.beginStream('pool-demo');
  assert.equal(pick.keyId, KEY_A);

  runtime.recordFailure('pool-demo', KEY_A, 'AUTH'); // failureCount=2 → 2000ms
  snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).cooldownRemainingMs, 2000);

  clock.value = 3000;
  runtime.recordSuccess('pool-demo', KEY_A);
  snap = runtime.healthSnapshot().pools.demo;
  const keyA = snap.keys.find((k) => k.keyId === KEY_A);
  assert.equal(keyA.state, 'ready');
  assert.equal(keyA.failureCount, 0);
});

test('RATE_LIMIT 受 Retry-After 抬升', () => {
  const { runtime } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_B, 'RATE_LIMIT', { retryAfterMs: 5000 });
  const snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_B).cooldownRemainingMs, 5000);
});

test('QUOTA 长冷却 = maxCooldownMs', () => {
  const { runtime } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_C, 'QUOTA');
  const snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_C).cooldownRemainingMs, 30000);
});

test('INVALID_CREDENTIAL 禁用后不再被选中；resetCooldown 恢复', async () => {
  const { runtime } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_A, 'INVALID_CREDENTIAL');
  let snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).state, 'disabled');
  for (let i = 0; i < 3; i += 1) {
    const pick = await runtime.beginStream('pool-demo');
    assert.notEqual(pick.keyId, KEY_A);
  }
  runtime.resetCooldown('pool-demo', KEY_A);
  snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).state, 'ready');
});

test('provider 级失败（TIMEOUT/TRANSPORT/SERVER/EMPTY_RESPONSE）不罚 Key', () => {
  const { runtime } = makeRuntime({ values: VALUES });
  for (const code of ['TIMEOUT', 'TRANSPORT', 'SERVER', 'EMPTY_RESPONSE']) {
    runtime.recordFailure('pool-demo', KEY_A, code);
    const snap = runtime.healthSnapshot().pools.demo;
    const keyA = snap.keys.find((k) => k.keyId === KEY_A);
    assert.equal(keyA.state, 'ready', code);
    assert.equal(keyA.failureCount, 0, code);
  }
  const snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.providerFailures, 4);
  assert.equal(snap.lastFailure.code, 'EMPTY_RESPONSE');
});

test('请求侧失败（INVALID_REQUEST 等）完全透传', () => {
  const { runtime } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_A, 'INVALID_REQUEST');
  runtime.recordFailure('pool-demo', KEY_A, 'CONTEXT_WINDOW_EXCEEDED');
  const snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.providerFailures, 0);
  assert.equal(snap.lastFailure, null);
  assert.equal(snap.keys.find((k) => k.keyId === KEY_A).state, 'ready');
});

test('凭据缺失的 Key 被跳过；全部缺失 → POOL_EXHAUSTED', async () => {
  const { runtime } = makeRuntime({ values: { [KEY_A]: 'sk-aaa' } });
  const pick = await runtime.beginStream('pool-demo');
  assert.equal(pick.keyId, KEY_A);
  const { runtime: empty } = makeRuntime({ values: {} });
  await assert.rejects(() => empty.beginStream('pool-demo'), (err) => err.code === POOL_EXHAUSTED_CODE);
});

test('resetCooldown(route) 重置整池', () => {
  const { runtime } = makeRuntime({ values: VALUES });
  runtime.recordFailure('pool-demo', KEY_A, 'AUTH');
  runtime.recordFailure('pool-demo', KEY_B, 'INVALID_CREDENTIAL');
  runtime.recordFailure('pool-demo', KEY_C, 'QUOTA');
  runtime.resetCooldown('pool-demo');
  const snap = runtime.healthSnapshot().pools.demo;
  for (const key of snap.keys) {
    assert.equal(key.state, 'ready');
    assert.equal(key.failureCount, 0);
  }
});

test('热替换配置：保留游标与同 Key 健康状态，移除消失的池', async () => {
  const { runtime } = makeRuntime({ values: VALUES });
  await runtime.beginStream('pool-demo'); // 游标 0
  await runtime.beginStream('pool-demo'); // 游标 1（KEY_B）
  runtime.recordFailure('pool-demo', KEY_B, 'AUTH'); // KEY_B 冷却

  runtime.replaceConfig(makeConfig()); // 相同 keyIds
  let snap = runtime.healthSnapshot().pools.demo;
  assert.equal(snap.keys.find((k) => k.keyId === KEY_B).state, 'cooling');

  const pick = await runtime.beginStream('pool-demo'); // 游标从 1 继续 → KEY_C
  assert.equal(pick.keyId, KEY_C);

  runtime.replaceConfig(validatePoolConfig({ pools: {} }));
  assert.deepEqual(runtime.healthSnapshot().pools, {});
  await assert.rejects(() => runtime.beginStream('pool-demo'), (err) => err.code === POOL_EXHAUSTED_CODE);
});

test('健康快照不含任何 Key 值', async () => {
  const { runtime } = makeRuntime({ values: VALUES });
  await runtime.beginStream('pool-demo');
  const text = JSON.stringify(runtime.healthSnapshot());
  assert.ok(!text.includes('sk-aaa') && !text.includes('sk-bbb') && !text.includes('sk-ccc'));
});
