import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  routeOf,
  isPoolRoute,
  validatePoolConfig,
  validateBaseURL,
  DEFAULT_COOLDOWN_MS,
  DEFAULT_MAX_COOLDOWN_MS,
  MIN_COOLDOWN_MS,
  MAX_COOLDOWN_MS,
  DEFAULT_MAX_RETRIES,
  MAX_MAX_RETRIES,
} from '../src/schema.js';

const minimalPool = (overrides = {}) => ({
  api: 'openai-completions',
  baseURL: 'https://api.example.com/v1',
  models: [{ id: 'model-a' }],
  keyIds: ['k-00000000-0000-4000-8000-000000000001'],
  ...overrides,
});

test('最小合法配置通过并填充默认值', () => {
  const config = validatePoolConfig({
    pools: { demo: minimalPool() },
  });
  assert.equal(config.schema, 'dsh.api-key-pool/v1');
  assert.equal(config.allowLoopbackHttpForTests, false);
  const pool = config.pools.demo;
  assert.equal(pool.displayName, 'demo');
  assert.equal(pool.selection, 'round-robin');
  assert.equal(pool.cooldownMs, DEFAULT_COOLDOWN_MS);
  assert.equal(pool.maxCooldownMs, DEFAULT_MAX_COOLDOWN_MS);
  assert.equal(pool.maxRetries, DEFAULT_MAX_RETRIES);
  assert.equal(pool.enabled, true);
  assert.deepEqual(pool.models, [
    { id: 'model-a', name: 'model-a', contextWindow: 262144, maxTokens: 32768 },
  ]);
});

test('空/undefined 配置返回空分节', () => {
  for (const input of [undefined, null]) {
    const config = validatePoolConfig(input);
    assert.deepEqual(config.pools, {});
    assert.equal(config.allowLoopbackHttpForTests, false);
  }
});

test('baseURL 白名单：仅 HTTPS；HTTP 仅在测试开关下放行 loopback', () => {
  assert.throws(() => validateBaseURL('http://api.example.com/v1'), /协议被拒绝/);
  assert.throws(() => validateBaseURL('ftp://api.example.com'), /协议被拒绝/);
  assert.throws(() => validateBaseURL('not-a-url'), /无法解析/);
  assert.throws(() => validatePoolConfig({ pools: { demo: minimalPool({ baseURL: 'http://api.example.com' }) } }), /协议被拒绝/);

  // 测试开关放行 loopback HTTP，但非 loopback HTTP 仍拒绝
  const loopback = validateBaseURL('http://127.0.0.1:9999/v1', { allowLoopbackHttpForTests: true });
  assert.equal(loopback.hostname, '127.0.0.1');
  assert.throws(() => validateBaseURL('http://api.example.com', { allowLoopbackHttpForTests: true }), /协议被拒绝/);
});

test('池 id 文法校验', () => {
  for (const bad of ['UPPER', 'a', '-abc', 'ab_', 'x'.repeat(41), '']) {
    assert.throws(() => validatePoolConfig({ pools: { [bad]: minimalPool() } }), /池 id 非法/, `id=${bad}`);
  }
  validatePoolConfig({ pools: { 'ab': minimalPool() } });
});

test('models 目录：非空/去重', () => {
  assert.throws(() => validatePoolConfig({ pools: { demo: minimalPool({ models: [] }) } }), /至少一条/);
  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm' }, { id: 'm' }] }) },
  }), /重复模型/);
  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: '' }] }) },
  }), /空模型 id/);
});

test('模型 input 模态：勾选识图补齐 text，仅文本不写盘，非法值拒绝', () => {
  const imageOnly = validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm', input: ['image'] }] }) },
  });
  assert.deepEqual(imageOnly.pools.demo.models[0].input, ['text', 'image']);

  const both = validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm', input: ['text', 'image'] }] }) },
  });
  assert.deepEqual(both.pools.demo.models[0].input, ['text', 'image']);

  // 未勾选与显式只写 text 同义：不落盘，交给适配器默认，避免无意义的字段漂移
  const textOnly = validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm', input: ['text'] }] }) },
  });
  assert.equal('input' in textOnly.pools.demo.models[0], false);
  const unset = validatePoolConfig({ pools: { demo: minimalPool({ models: [{ id: 'm' }] }) } });
  assert.equal('input' in unset.pools.demo.models[0], false);

  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm', input: ['vision'] }] }) },
  }), /不支持的模态/);
  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ models: [{ id: 'm', input: 'image' }] }) },
  }), /必须是数组/);
});

test('keyIds 文法与去重', () => {
  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ keyIds: ['not-a-key'] }) },
  }), /keyId 非法/);
  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ keyIds: ['k-00000000-0000-4000-8000-000000000001', 'k-00000000-0000-4000-8000-000000000001'] }) },
  }), /重复 keyId/);
});

test('数值边界：越界回退默认，cooldownMs > maxCooldownMs 拒绝', () => {
  const tooSmall = validatePoolConfig({ pools: { demo: minimalPool({ cooldownMs: MIN_COOLDOWN_MS - 1 }) } });
  assert.equal(tooSmall.pools.demo.cooldownMs, DEFAULT_COOLDOWN_MS);

  const tooLarge = validatePoolConfig({ pools: { demo: minimalPool({ cooldownMs: MAX_COOLDOWN_MS + 1 }) } });
  assert.equal(tooLarge.pools.demo.cooldownMs, DEFAULT_COOLDOWN_MS);

  const retries = validatePoolConfig({ pools: { demo: minimalPool({ maxRetries: MAX_MAX_RETRIES + 1 }) } });
  assert.equal(retries.pools.demo.maxRetries, DEFAULT_MAX_RETRIES);

  assert.throws(() => validatePoolConfig({
    pools: { demo: minimalPool({ cooldownMs: 60_000, maxCooldownMs: 30_000 }) },
  }), /cooldownMs 超过 maxCooldownMs/);
});

test('api 枚举与 selection 仅 round-robin', () => {
  assert.throws(() => validatePoolConfig({ pools: { demo: minimalPool({ api: 'grpc' }) } }), /不受支持/);
  assert.throws(() => validatePoolConfig({ pools: { demo: minimalPool({ selection: 'weighted' }) } }), /仅支持 round-robin/);
  validatePoolConfig({ pools: { demo: minimalPool({ api: 'anthropic-messages' }) } });
});

test('route 派生与判定', () => {
  assert.equal(routeOf('demo'), 'pool-demo');
  assert.equal(isPoolRoute('pool-demo'), true);
  assert.equal(isPoolRoute('deepseek'), false);
  assert.equal(isPoolRoute(undefined), false);
});
