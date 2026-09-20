// M02/M03 行为回归：轮询游标每请求只推进一次；故障转移按真实内容事件决策并冷却失败 Key。
// 使用注入的模拟 attempt（不触网、不读真实凭据），事件协议与 pi-ai AssistantMessageEvent 一致。
import test from 'node:test';
import assert from 'node:assert/strict';
import { failoverStream, createKeyPool } from '../lib/index.js';
import { createAssistantMessageEventStream } from '@earendil-works/pi-ai/utils/event-stream';

const KIND = 'stream';
const MODEL = {};
const CONTEXT = {};
const OPTIONS = {};

function errorEvent(message) {
  return {
    type: 'error',
    reason: 'error',
    error: { role: 'assistant', api: 'openai-completions', provider: 'cline', model: 'unknown', stopReason: 'error', errorMessage: message, content: [] },
  };
}

function makePool(keys, opts = {}) {
  const cooldownUntil = new Map();
  const config = { apiKeyEnv: 'LEGACY', apiKeyEnvPool: keys };
  const ctx = {
    get: () => ({ resolve: async ref => keys.includes(String(ref)) ? { value: String(ref) } : undefined }),
    logger: { warn: opts.warn ?? (() => {}) },
  };
  const pool = createKeyPool(ctx, () => config);
  const cool = pool.cool;
  pool.cool = (key, ms) => { cooldownUntil.set(key, Date.now() + ms); cool(key, ms); };
  return Object.assign(pool, { cooldownUntil });
}

function fakeAttempt(scriptFor) {
  const calls = [];
  const fn = (kind, model, context, options, apiKey) => {
    calls.push(apiKey);
    const stream = createAssistantMessageEventStream();
    void (async () => {
      for (const ev of scriptFor(apiKey, calls.length)) {
        stream.push(ev);
        if (ev.type === 'error' || ev.type === 'done') return;
        await new Promise(resolve => setImmediate(resolve));
      }
      stream.end();
    })();
    return stream;
  };
  fn.calls = calls;
  return fn;
}

async function collect(stream) {
  const events = [];
  for await (const ev of stream) events.push(ev);
  return events;
}

test('M02: peek 不推进游标，usableKeys 每请求只推进一次，2 把 Key 连续 4 请求交替', async () => {
  const pool = makePool(['A', 'B']);
  // 预检（peek）任意多次不改变轮询起点。
  await pool.peekUsableKeys();
  await pool.peekUsableKeys();
  await pool.peekUsableKeys();
  assert.deepEqual(await pool.peekUsableKeys(), ['A', 'B']);
  assert.deepEqual(await pool.usableKeys(), ['A', 'B'], '首次分配从 A 开始');
  assert.deepEqual(await pool.usableKeys(), ['B', 'A'], '第二次分配从 B 开始');
  assert.deepEqual(await pool.usableKeys(), ['A', 'B']);
  assert.deepEqual(await pool.usableKeys(), ['B', 'A']);
  // 实际调用链：failoverStream 每请求只调用一次 usableKeys，发送 keys[0]。
  const attempt = fakeAttempt(key => [{ type: 'done', message: {} }]);
  for (let i = 0; i < 4; i++) {
    await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  }
  assert.deepEqual(attempt.calls, ['A', 'B', 'A', 'B'], '连续 4 请求发送选择必须交替');
});

test('M02: 4 把 Key 连续 8 请求，每把 Key 均获得分配', async () => {
  const pool = makePool(['A', 'B', 'C', 'D']);
  const attempt = fakeAttempt(key => [{ type: 'done', message: {} }]);
  for (let i = 0; i < 8; i++) {
    await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  }
  assert.deepEqual(attempt.calls, ['A', 'B', 'C', 'D', 'A', 'B', 'C', 'D']);
});

test('M03: start→error(401) 视为零内容，切换并冷却 fakeA', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt((key) => {
    if (key === 'fakeA') return [{ type: 'start' }, errorEvent('HTTP 401 unauthorized')];
    return [{ type: 'start' }, { type: 'text_delta', delta: 'ok' }, { type: 'done', message: {} }];
  });
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA', 'fakeB'], 'start 后失败必须切换到下一把');
  assert.ok(pool.cooldownUntil.has('fakeA'), 'fakeA 必须被冷却');
  assert.ok(!pool.cooldownUntil.has('fakeB'), '成功的 fakeB 不得被冷却');
  assert.equal(events.filter(e => e.type === 'error').length, 0);
});

test('M03: 纯 error 序列，A 失败切 B，B 也失败则两个 Key 都被冷却并明确终止', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt(() => [errorEvent('HTTP 401 unauthorized')]);
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA', 'fakeB']);
  assert.ok(pool.cooldownUntil.has('fakeA') && pool.cooldownUntil.has('fakeB'), '最终失败的 B 也必须被冷却');
  const errors = events.filter(e => e.type === 'error');
  assert.equal(errors.length, 1, '必须恰好一个终止错误');
  assert.match(errors[0].error.errorMessage, /401/);
  assert.ok(!attempt.calls.includes(undefined), '不得退回未指定池 Key 的额外尝试');
});

test('M03: 文本内容后失败不重放，透传真实失败但仍冷却', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt((key) => {
    if (key === 'fakeA') return [{ type: 'start' }, { type: 'text_delta', delta: 'partial' }, errorEvent('HTTP 429 rate limit')];
    return [{ type: 'done', message: {} }];
  });
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA'], '已产出内容后不得重放');
  assert.ok(pool.cooldownUntil.has('fakeA'), '失败 Key 必须被冷却（即使不重放）');
  assert.ok(events.some(e => e.type === 'text_delta'));
  const errors = events.filter(e => e.type === 'error');
  assert.equal(errors.length, 1);
  assert.match(errors[0].error.errorMessage, /429/);
});

test('M03: 工具调用内容后失败同样不重放', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt(key => (
    key === 'fakeA'
      ? [{ type: 'toolcall_start', id: 't1', toolName: 'bash' }, errorEvent('HTTP 403 forbidden')]
      : [{ type: 'done', message: {} }]
  ));
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA']);
  assert.ok(pool.cooldownUntil.has('fakeA'));
  assert.ok(events.some(e => e.type === 'toolcall_start'));
});

test('M03: 不可重试错误不冷却、不切换，直接透传', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt(() => [errorEvent('internal server error 500')]);
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA']);
  assert.equal(pool.cooldownUntil.size, 0, '不可重试错误不得冷却');
  const errors = events.filter(e => e.type === 'error');
  assert.equal(errors.length, 1);
});

test('M03: 冷却分类——401 用 invalid 冷却，429 用普通冷却', async () => {
  const poolA = makePool(['kA']);
  const attemptA = fakeAttempt(() => [errorEvent('HTTP 401 unauthorized')]);
  await collect(failoverStream(KIND, poolA, MODEL, CONTEXT, OPTIONS, attemptA));
  const invalidMs = poolA.cooldownUntil.get('kA') - Date.now();
  assert.ok(invalidMs > 1_000_000, '401 必须使用长 invalid 冷却');

  const poolB = makePool(['kB']);
  const attemptB = fakeAttempt(() => [errorEvent('HTTP 429 too many requests')]);
  await collect(failoverStream(KIND, poolB, MODEL, CONTEXT, OPTIONS, attemptB));
  const normalMs = poolB.cooldownUntil.get('kB') - Date.now();
  assert.ok(normalMs > 0 && normalMs <= 120_000, '429 必须使用普通冷却');
});

test('M03: 全冷却/空池明确终止，不发起任何尝试', async () => {
  const pool = makePool(['A', 'B']);
  const attempt = fakeAttempt(() => [{ type: 'done', message: {} }]);
  pool.cool('A', 60_000);
  pool.cool('B', 60_000);
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, [], '全冷却时不得发起请求');
  const errors = events.filter(e => e.type === 'error');
  assert.equal(errors.length, 1);
  assert.match(errors[0].error.errorMessage, /cooling down|missing/);
});

test('M03: 最后一把 Key 失败不切换，透传错误且被冷却', async () => {
  const pool = makePool(['fakeA', 'fakeB']);
  const attempt = fakeAttempt(key => (
    key === 'fakeA' ? [errorEvent('HTTP 401 unauthorized')] : [errorEvent('HTTP 401 unauthorized')]
  ));
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['fakeA', 'fakeB']);
  assert.ok(pool.cooldownUntil.has('fakeA') && pool.cooldownUntil.has('fakeB'));
  const errors = events.filter(e => e.type === 'error');
  assert.equal(errors.length, 1, '最后一把失败时必须透传恰好一个错误');
  assert.ok(!attempt.calls.includes(undefined), '不得退回未指定池 Key 的额外尝试');
});

test('M03: 消费端提前中断（取消）不造成错误重复发送', async () => {
  const pool = makePool(['fakeA']);
  const attempt = fakeAttempt(() => [
    { type: 'start' },
    { type: 'text_delta', delta: 'chunk1' },
    { type: 'text_delta', delta: 'chunk2' },
    { type: 'done', message: {} },
  ]);
  const stream = failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt);
  const seen = [];
  for await (const ev of stream) {
    seen.push(ev.type);
    if (ev.type === 'text_delta') break;
  }
  assert.deepEqual(seen, ['start', 'text_delta']);
  await new Promise(resolve => setImmediate(resolve));
});

test('预取消信号不分配Key、不发请求，保留aborted协议', async () => {
  const pool = makePool(['A', 'B']);
  const controller = new AbortController();
  controller.abort();
  const attempt = fakeAttempt(() => [{ type: 'done', message: {} }]);
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, { signal: controller.signal }, attempt));
  assert.deepEqual(attempt.calls, []);
  assert.equal(events.length, 1);
  assert.equal(events[0].reason, 'aborted');
  assert.deepEqual(await pool.usableKeys(), ['A', 'B']);
});

test('401到达时信号已取消，不冷却也不请求下一把', async () => {
  const pool = makePool(['A', 'B']);
  const controller = new AbortController();
  const attempt = fakeAttempt(() => { controller.abort(); return [errorEvent('HTTP 401 unauthorized')]; });
  const events = await collect(failoverStream(KIND, pool, MODEL, CONTEXT, { signal: controller.signal }, attempt));
  assert.deepEqual(attempt.calls, ['A']);
  assert.equal(pool.cooldownUntil.size, 0);
  assert.deepEqual(events.map(event => event.reason), ['aborted']);
});

test('空文本delta后401仍可切换，尚未输出真实内容', async () => {
  const pool = makePool(['A', 'B']);
  const attempt = fakeAttempt(key => key === 'A'
    ? [{ type: 'text_delta', delta: '' }, errorEvent('HTTP 401 unauthorized')]
    : [{ type: 'done', message: {} }]);
  await collect(failoverStream(KIND, pool, MODEL, CONTEXT, OPTIONS, attempt));
  assert.deepEqual(attempt.calls, ['A', 'B']);
});

test('生产池仅解析active refs，待清理列表不进入模型请求', async () => {
  const resolved = [];
  const pool = createKeyPool({ get: () => ({ resolve: async ref => { resolved.push(String(ref)); return { value: String(ref) }; } }), logger: { warn() {} } },
    () => ({ apiKeyEnv: 'LEGACY', apiKeyEnvPool: ['ACTIVE'], apiKeyCleanupRefs: ['STALE'] }));
  assert.deepEqual(await pool.usableKeys(), ['LEGACY', 'ACTIVE']);
  assert.deepEqual(resolved, ['LEGACY', 'ACTIVE']);
});
