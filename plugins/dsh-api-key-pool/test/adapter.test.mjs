import test from 'node:test';
import assert from 'node:assert/strict';
import { LlmError } from '@deepseek-ai/dsh-llm';
import { PiAiAdapter } from '@deepseek-ai/dsh-llm-pi-ai';
import { KeyPoolRuntime, POOL_EXHAUSTED_CODE } from '../src/pools.js';
import { validatePoolConfig } from '../src/schema.js';
import {
  PoolPiAiAdapter,
  resolvePoolProfiles,
  makeResolveApiKey,
  keySession,
} from '../src/adapter.js';

// ---------------------------------------------------------------------------
// 测试夹具：全部为 sk- 占位符 Key，非真实凭据。
// ---------------------------------------------------------------------------

const KEY_COUNT = 5;
const KEY_IDS = Array.from({ length: KEY_COUNT }, (_, i) =>
  `k-0000000${i}-0000-4000-8000-00000000000${i}`);
const KEY_VALUES = new Map(KEY_IDS.map((id, i) => [id, `sk-test-pool-placeholder-${i}000`]));

function makeConfig(extra = {}) {
  return validatePoolConfig({
    schema: 'dsh.api-key-pool/v1',
    pools: {
      main: {
        api: 'openai-completions',
        baseURL: 'https://api.example.com',
        models: [{ id: 'm-1', name: '模型一' }],
        keyIds: [...KEY_IDS],
        cooldownMs: 1000,
        maxCooldownMs: 10000,
        ...extra,
      },
    },
  });
}

function makeRuntime(config = makeConfig()) {
  return new KeyPoolRuntime({
    config,
    resolveKey: async (keyId) => KEY_VALUES.get(keyId),
  });
}

async function consume(gen, sink) {
  for await (const chunk of gen) sink.push(chunk);
}

// ---------------------------------------------------------------------------
// 父类流打桩：模拟 PiAiAdapter.streamWithSnapshot 的 Key 消费面（ALS）。
// 每个 chunk 都经 resolveApiKey 取一次 Key，并嵌入 chunk.text 供断言。
// ---------------------------------------------------------------------------

function stubParentStream(script) {
  const queue = [...script];
  const original = PiAiAdapter.prototype.streamWithSnapshot;
  PiAiAdapter.prototype.streamWithSnapshot = async function* (options) {
    const behavior = queue.shift() ?? { kind: 'ok' };
    const readKey = async () => this.config.resolveApiKey(options.provider, {});
    if (behavior.kind === 'throw') {
      await readKey();
      throw behavior.error;
    }
    const chunks = behavior.kind === 'auth-finish'
      ? [{ type: 'text-delta', text: await readKey() }, { type: 'finish', reason: { failure: { code: 'AUTH' } } }]
      : [{ type: 'text-delta', text: await readKey() }, { type: 'text-delta', text: await readKey() },
        { type: 'finish', reason: { usage: {} } }];
    for (const chunk of chunks) yield chunk;
  };
  return () => { PiAiAdapter.prototype.streamWithSnapshot = original; };
}

test('makeResolveApiKey：ALS 会话外抛稳定 code，会话内返回快照值', async () => {
  const resolve = makeResolveApiKey();
  await assert.rejects(
    () => resolve('pool-main'),
    (error) => error instanceof LlmError && error.code === 'POOL_KEY_CONTEXT_MISSING',
  );
  const value = await keySession.run({ value: 'sk-test-x' }, () => resolve('pool-main'));
  assert.equal(value, 'sk-test-x');
});

test('resolvePoolProfiles：route/profile 字段与 piProvider 模型目录完整', () => {
  const profiles = resolvePoolProfiles(makeConfig());
  assert.deepEqual([...profiles.keys()], ['pool-main']);
  const profile = profiles.get('pool-main');
  assert.equal(profile.provider, 'pool-main');
  assert.equal(profile.displayName, 'main');
  assert.equal(typeof profile.streamIdleTimeoutMs, 'number');
  assert.equal(typeof profile.maxRequestImageBytes, 'number');
  assert.equal(typeof profile.retryPolicy, 'object');
  assert.equal(profile.configuredMaxTokens.get('m-1'), 32768);
  const models = profile.piProvider.getModels();
  assert.equal(models.length, 1);
  assert.equal(models[0].id, 'm-1');
  assert.equal(models[0].provider, 'pool-main');
  assert.deepEqual(models[0].input, ['text']);
  assert.equal(profile.piProvider.auth.apiKey.name, 'main');
});

test('resolvePoolProfiles：勾选识图的模型声明 [text, image]，未勾选仍只声明文本', () => {
  const config = validatePoolConfig({
    schema: 'dsh.api-key-pool/v1',
    pools: {
      vision: {
        api: 'openai-completions',
        baseURL: 'https://api.example.com',
        models: [{ id: 'see', input: ['text', 'image'] }, { id: 'plain' }],
        keyIds: [KEY_IDS[0]],
      },
    },
  });
  const models = resolvePoolProfiles(config).get('pool-vision').piProvider.getModels();
  assert.deepEqual(models.find((model) => model.id === 'see').input, ['text', 'image']);
  assert.deepEqual(models.find((model) => model.id === 'plain').input, ['text']);
});

test('PoolPiAiAdapter：把 Harness 持久附件服务 resolver 原样交给官方父类', () => {
  const attachments = { readImageRequest: async () => ({}) };
  let calls = 0;
  const adapter = new PoolPiAiAdapter({
    pools: makeRuntime(),
    profiles: () => resolvePoolProfiles(makeConfig()),
    resolveAttachments: () => { calls += 1; return attachments; },
  });
  // 官方父类在含图请求时调用 config.resolveAttachments；此前这里固定为 undefined，
  // 会在任何网络请求前抛 “requires the durable attachment service”。
  assert.equal(adapter.config.resolveAttachments(), attachments);
  assert.equal(calls, 1);
});

test('真实父类含图前置链路：识图模型进入附件服务，文本模型仍在附件读取前拒绝', async () => {
  const config = validatePoolConfig({
    schema: 'dsh.api-key-pool/v1',
    pools: {
      vision: {
        api: 'openai-completions',
        baseURL: 'https://api.example.com',
        models: [{ id: 'see', input: ['text', 'image'] }, { id: 'plain' }],
        keyIds: [KEY_IDS[0]],
      },
    },
  });
  let attachmentReads = 0;
  const marker = new Error('ATTACHMENT_SERVICE_REACHED');
  const adapter = new PoolPiAiAdapter({
    pools: makeRuntime(config),
    profiles: () => resolvePoolProfiles(config),
    resolveAttachments: () => ({
      async readImageRequest() { attachmentReads += 1; throw marker; },
    }),
  });
  const messages = [{
    role: 'user',
    content: [{
      type: 'image',
      attachment: { attachmentId: 'att-test-1', mediaType: 'image/png', bytes: 128 },
    }],
  }];

  await assert.rejects(
    () => adapter.streamWithSnapshot({ provider: 'pool-vision', model: 'see', messages }, adapter.current()).next(),
    (error) => error === marker,
  );
  assert.equal(attachmentReads, 1);

  await assert.rejects(
    () => adapter.streamWithSnapshot({ provider: 'pool-vision', model: 'plain', messages }, adapter.current()).next(),
    (error) => error instanceof LlmError && error.code === 'UNSUPPORTED_CONTENT' && /does not support image input/.test(error.message),
  );
  assert.equal(attachmentReads, 1, '文本模型必须在读取附件前拒绝');
});

test('100 并发 mock 流：Key 严格轮询分布且流内 Key 恒定不变', async () => {
  const restore = stubParentStream([{ kind: 'ok' }]);
  try {
    const runtime = makeRuntime();
    const adapter = new PoolPiAiAdapter({ pools: runtime, profiles: () => new Map() });
    const results = await Promise.all(Array.from({ length: 100 }, () => {
      const seen = [];
      return consume(adapter.streamWithSnapshot({ provider: 'pool-main', model: 'm-1', messages: [] }, {}), seen)
        .then(() => seen);
    }));
    const counts = new Map();
    for (const chunks of results) {
      // 流内不变：同一条流的所有 text-delta chunk 嵌入同一个 Key
      const keys = new Set(chunks.filter((chunk) => chunk.type === 'text-delta').map((chunk) => chunk.text));
      assert.equal(keys.size, 1, `流内 Key 必须恒定：${[...keys].join(' vs ')}`);
      const key = [...keys][0];
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    // 分布：5 Key × 各 20 次，无挤兑
    assert.equal(counts.size, KEY_COUNT);
    for (const [key, count] of counts) {
      assert.equal(count, 100 / KEY_COUNT, `Key ${key.slice(-4)} 分布应为 20，实际 ${count}`);
    }
    // 全部成功：健康快照无失败
    const snapshot = runtime.healthSnapshot();
    assert.equal(snapshot.pools.main.providerFailures, 0);
    assert.ok(snapshot.pools.main.keys.every((k) => k.state === 'ready' && k.failureCount === 0));
  } finally {
    restore();
  }
});

test('AUTH finish：该 Key 进入冷却，后续流自动换 Key', async () => {
  const restore = stubParentStream([{ kind: 'auth-finish' }, { kind: 'ok' }]);
  try {
    const runtime = makeRuntime();
    const adapter = new PoolPiAiAdapter({ pools: runtime, profiles: () => new Map() });
    const options = { provider: 'pool-main', model: 'm-1', messages: [] };

    const first = [];
    await consume(adapter.streamWithSnapshot(options, {}), first);
    // finish reason.failure.code=AUTH → recordFailure（冷却）
    const after = runtime.healthSnapshot().pools.main;
    assert.equal(after.keys[0].state, 'cooling');
    assert.equal(after.keys[0].failureCount, 1);
    assert.ok(after.keys[0].cooldownRemainingMs > 0);

    // 下一条流必须换到第二个 Key（游标已越过冷却中的首 Key）
    const second = [];
    await consume(adapter.streamWithSnapshot(options, {}), second);
    assert.notEqual(second[0].text, first[0].text);
    assert.equal(runtime.healthSnapshot().pools.main.keys[0].failureCount, 1);
  } finally {
    restore();
  }
});

test('三类流失败合法终止：INVALID_CREDENTIAL 禁用、TIMEOUT 只计数、POOL_EXHAUSTED 透传', async () => {
  const restore = stubParentStream([
    { kind: 'throw', error: new LlmError('invalid credential', 'INVALID_CREDENTIAL') },
    { kind: 'throw', error: new LlmError('upstream timeout', 'TIMEOUT') },
  ]);
  try {
    const runtime = makeRuntime();
    const adapter = new PoolPiAiAdapter({ pools: runtime, profiles: () => new Map() });
    const options = { provider: 'pool-main', model: 'm-1', messages: [] };

    // 1) INVALID_CREDENTIAL → 禁用该 Key
    await assert.rejects(
      () => consume(adapter.streamWithSnapshot(options, {}), []),
      (error) => error instanceof LlmError && error.code === 'INVALID_CREDENTIAL',
    );
    let health = runtime.healthSnapshot().pools.main;
    assert.equal(health.keys[0].state, 'disabled');
    assert.equal(health.keys[0].failureCount, 1);

    // 2) TIMEOUT → provider 级计数，不罚 Key（第二个 Key 保持 ready）
    await assert.rejects(
      () => consume(adapter.streamWithSnapshot(options, {}), []),
      (error) => error instanceof LlmError && error.code === 'TIMEOUT',
    );
    health = runtime.healthSnapshot().pools.main;
    assert.equal(health.providerFailures, 1);
    assert.equal(health.keys[1].state, 'ready');

    // 3) 全部 Key 不可用 → POOL_EXHAUSTED 合法终止（不记为 Key 失败）
    for (const keyId of KEY_IDS) runtime.recordFailure('pool-main', keyId, 'INVALID_CREDENTIAL');
    await assert.rejects(
      () => consume(adapter.streamWithSnapshot(options, {}), []),
      (error) => error instanceof LlmError && error.code === POOL_EXHAUSTED_CODE,
    );
  } finally {
    restore();
  }
});

test('成功流清零失败计数；未知 route 抛 POOL_EXHAUSTED', async () => {
  const restore = stubParentStream([{ kind: 'ok' }]);
  try {
    let clock = 1_000_000;
    const runtime = new KeyPoolRuntime({
      config: makeConfig(),
      resolveKey: async (keyId) => KEY_VALUES.get(keyId),
      now: () => clock,
    });
    const adapter = new PoolPiAiAdapter({ pools: runtime, profiles: () => new Map() });
    runtime.recordFailure('pool-main', KEY_IDS[0], 'RATE_LIMIT');
    assert.ok(runtime.healthSnapshot().pools.main.keys[0].failureCount > 0);
    clock += 2_000; // 冷却过期，首个 Key 重新可用
    await consume(adapter.streamWithSnapshot({ provider: 'pool-main', model: 'm-1', messages: [] }, {}), []);
    assert.equal(runtime.healthSnapshot().pools.main.keys[0].failureCount, 0);

    await assert.rejects(
      () => consume(adapter.streamWithSnapshot({ provider: 'pool-not-exist', model: 'm-1', messages: [] }, {}), []),
      (error) => error instanceof LlmError && error.code === POOL_EXHAUSTED_CODE,
    );
  } finally {
    restore();
  }
});

test('调用方取消：父流在同一 ALS Key 快照中关闭，且不惩罚 Key', async () => {
  const original = PiAiAdapter.prototype.streamWithSnapshot;
  let keySeenDuringDispose;
  PiAiAdapter.prototype.streamWithSnapshot = async function* (options) {
    try {
      yield { type: 'text-delta', text: await this.config.resolveApiKey(options.provider, {}) };
      yield { type: 'text-delta', text: '不应消费' };
    } finally {
      keySeenDuringDispose = await this.config.resolveApiKey(options.provider, {});
    }
  };
  try {
    const runtime = makeRuntime();
    const adapter = new PoolPiAiAdapter({ pools: runtime, profiles: () => new Map() });
    const stream = adapter.streamWithSnapshot({ provider: 'pool-main', model: 'm-1', messages: [] }, {});
    const first = await stream.next();
    assert.equal(first.done, false);
    await stream.return(undefined);
    assert.equal(keySeenDuringDispose, first.value.text);
    const health = runtime.healthSnapshot().pools.main;
    assert.equal(health.providerFailures, 0);
    assert.ok(health.keys.every((key) => key.state === 'ready' && key.failureCount === 0));
  } finally {
    PiAiAdapter.prototype.streamWithSnapshot = original;
  }
});
