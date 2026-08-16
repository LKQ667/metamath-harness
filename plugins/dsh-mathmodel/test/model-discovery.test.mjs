import test from 'node:test';
import assert from 'node:assert/strict';
import { StoredKeyModelDiscoveryService } from '../lib/index.js';

const profile = {
  apiKeyEnv: 'FIXTURE_PROVIDER_API_KEY',
  api: 'openai-completions',
  baseURL: 'https://gateway.example/v1',
};

function service({ credential = { value: 'fixture-secret' }, response = { ok: true, json: async () => ({ data: [{ id: 'alpha', name: 'Alpha' }, { id: 'alpha' }, { id: 'beta' }] }) } } = {}) {
  let request;
  const instance = new StoredKeyModelDiscoveryService({
    settings: { get: () => ({ providers: { fixture: profile } }) },
    credentials: { resolve: async () => credential },
    fetchImpl: async (url, init) => { request = { url, init }; return response; },
  });
  return { instance, request: () => request };
}

test('已保存的受管 Key 可用于再次获取自定义供应商模型，且不返回 Key', async () => {
  const fixture = service();
  const result = await fixture.instance.discover('fixture');
  assert.equal(fixture.request().url, 'https://gateway.example/v1/models');
  assert.equal(fixture.request().init.headers.authorization, 'Bearer fixture-secret');
  assert.deepEqual(result, { provider: 'fixture', models: [{ id: 'alpha', name: 'Alpha' }, { id: 'beta' }] });
  assert.doesNotMatch(JSON.stringify(result), /fixture-secret/);
});

test('缺少已保存 Key 时失败关闭，不向模型列表端点发请求', async () => {
  let calls = 0;
  const instance = new StoredKeyModelDiscoveryService({
    settings: { get: () => ({ providers: { fixture: profile } }) },
    credentials: { resolve: async () => undefined },
    fetchImpl: async () => { calls += 1; },
  });
  await assert.rejects(() => instance.discover('fixture'), (error) => error.code === 'credential_missing');
  assert.equal(calls, 0);
});

test('模型列表端点 401 不误报聊天模型或 Key 无效，错误中不含 Key', async () => {
  const fixture = service({ response: { ok: false, status: 401 } });
  await assert.rejects(() => fixture.instance.discover('fixture'), (error) => {
    assert.equal(error.code, 'models_endpoint_rejected');
    assert.match(error.message, /模型列表接口拒绝/);
    assert.doesNotMatch(error.message, /fixture-secret|API Key 无效/);
    return true;
  });
});
