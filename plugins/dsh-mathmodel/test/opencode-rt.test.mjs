import test from 'node:test';
import assert from 'node:assert/strict';
import { OpenCodeRtService, buildOpenCodeRtProfile, parseOpenCodeModels } from '../lib/index.js';

class Settings {
  constructor() {
    this.data = { 'llm-pi-ai': { providers: {} }, 'mathmodel-opencode-rt': { verifiedVisionModels: [] } };
  }
  get(namespace) { return this.data[namespace]; }
  async update(namespace, patch) { this.data[namespace] = { ...this.data[namespace], ...patch }; }
  async mutate(namespace, ops) {
    for (const operation of ops) {
      let cursor = this.data[namespace];
      for (const part of operation.path.slice(0, -1)) cursor = cursor[part] ??= {};
      cursor[operation.path.at(-1)] = operation.value;
    }
  }
}

test('只采纳协议注册表中的 chat-completions 模型，未知模型保持待支持', async () => {
  const settings = new Settings();
  const service = new OpenCodeRtService({
    settings,
    credentials: { resolve: async () => undefined },
    fetchImpl: async () => ({ ok: true, json: async () => ({ object: 'list', data: [{ id: 'glm-5.3' }, { id: 'kimi-k3' }, { id: 'gpt-5.6-luna' }] }) }),
  });
  const status = await service.refresh();
  assert.deepEqual(status.configuredModels, ['glm-5.3', 'kimi-k3']);
  assert.deepEqual(status.last.pending, ['gpt-5.6-luna']);
  assert.equal(settings.get('llm-pi-ai').providers['opencode-rt'].api, 'openai-completions');
  assert.deepEqual(settings.get('llm-pi-ai').providers['opencode-rt'].defaultInput, ['text']);
  assert.deepEqual(settings.get('llm-pi-ai').providers['opencode-rt'].models[1].input, ['text', 'image']);
});

test('添加提供方时保存凭据并立即从官方模型接口同步', async () => {
  const settings = new Settings();
  const saved = [];
  const service = new OpenCodeRtService({
    settings,
    credentials: { set: async (ref, value) => saved.push([ref, value]) },
    fetchImpl: async () => ({ ok: true, json: async () => ({ object: 'list', data: [{ id: 'kimi-k3' }] }) }),
  });
  const result = await service.configure('fixture-key');
  assert.deepEqual(saved, [['OPENCODE_GO_API_KEY', 'fixture-key']]);
  assert.deepEqual(result.configuredModels, ['kimi-k3']);
  assert.deepEqual(settings.get('llm-pi-ai').providers['opencode-rt'].models[0].input, ['text', 'image']);
});

test('添加提供方可复用既有 opencode-go 凭据而不重复写入', async () => {
  const settings = new Settings();
  let writes = 0;
  const service = new OpenCodeRtService({
    settings,
    credentials: { resolve: async () => ({ value: 'existing-fixture-key' }), set: async () => { writes += 1; } },
    fetchImpl: async () => ({ ok: true, json: async () => ({ object: 'list', data: [{ id: 'glm-5.3' }] }) }),
  });
  await service.configure('');
  assert.equal(writes, 0);
  assert.deepEqual(service.configuredModels(), ['glm-5.3']);
});

test('已声明的识图模型可发送图片，验收结果不含密钥', async () => {
  const settings = new Settings();
  settings.data['llm-pi-ai'].providers['opencode-rt'] = buildOpenCodeRtProfile(['kimi-k3']);
  const secret = 'opencode-fixture-secret';
  let request;
  const service = new OpenCodeRtService({
    settings,
    credentials: { resolve: async () => ({ value: secret }) },
    fetchImpl: async (_url, init) => { request = init; return { ok: true, json: async () => ({ choices: [{ message: { content: 'OK' } }] }) }; },
  });
  const result = await service.verifyVision('kimi-k3');
  assert.deepEqual(result, { model: 'kimi-k3', verified: true });
  assert.match(request.headers.authorization, /^Bearer /);
  assert.match(request.body, /image_url/);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(secret));
  assert.deepEqual(settings.get('llm-pi-ai').providers['opencode-rt'].models[0].input, ['text', 'image']);
});

test('未声明或未配置密钥时失败关闭且不产生网络请求', async () => {
  const settings = new Settings();
  settings.data['llm-pi-ai'].providers['opencode-rt'] = buildOpenCodeRtProfile(['kimi-k3']);
  let calls = 0;
  const service = new OpenCodeRtService({ settings, credentials: { resolve: async () => undefined }, fetchImpl: async () => { calls += 1; } });
  await assert.rejects(() => service.verifyVision('glm-5.3'), (error) => error.code === 'vision_not_declared');
  await assert.rejects(() => service.verifyVision('kimi-k3'), (error) => error.code === 'credential_missing');
  assert.equal(calls, 0);
});

test('模型清单格式必须合法且无重复 ID', () => {
  assert.deepEqual(parseOpenCodeModels({ object: 'list', data: [{ id: 'b' }, { id: 'a' }] }), ['a', 'b']);
  assert.throws(() => parseOpenCodeModels({ object: 'list', data: [{ id: 'a' }, { id: 'a' }] }), (error) => error.code === 'invalid_models_response');
});
