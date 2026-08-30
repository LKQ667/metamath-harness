import test from 'node:test';
import assert from 'node:assert/strict';
import { describeGrokCredential, resolveGrokSession } from '../src/image/grok-auth.js';
import { grokImagesAdapter } from '../src/image/adapters.js';
import { templateById, validateConnectionDraft } from '../src/security/image-connections.js';

function service({ configured = true, sessions = [] } = {}) {
  const calls = [];
  return {
    calls,
    async describe(provider) { calls.push({ method: 'describe', provider }); return { configured }; },
    async resolve(provider, options) {
      calls.push({ method: 'resolve', provider, options });
      return sessions.shift() ?? { accessToken: 'access-live' };
    },
  };
}

test('resolveGrokSession：只通过 Host service 解析且不暴露 refresh token', async () => {
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-live', refreshToken: 'never-forward' }] });
  const result = await resolveGrokSession({ subscriptionSessions, force: true });
  assert.deepEqual(result, { accessToken: 'access-live' });
  assert.equal('refreshToken' in result, false);
  assert.deepEqual(subscriptionSessions.calls.map((call) => [call.method, call.provider, call.options?.force]), [['resolve', 'grok', true]]);
});

test('resolveGrokSession：服务缺失与坏会话失败关闭', async () => {
  await assert.rejects(() => resolveGrokSession(), (error) => error.code === 'subscription_service_unavailable');
  await assert.rejects(
    () => resolveGrokSession({ subscriptionSessions: service({ sessions: [{}] }) }),
    (error) => error.code === 'subscription_session_invalid',
  );
});

test('describeGrokCredential：仅返回脱敏状态，服务缺失视为未就绪', async () => {
  assert.deepEqual(await describeGrokCredential(), {
    ref: 'subscriptions-auth', configured: false, writable: false, source: 'subscriptions-auth',
  });
  const info = await describeGrokCredential(service({ configured: true }));
  assert.deepEqual(info, { ref: 'subscriptions-auth', configured: true, writable: false, source: 'subscriptions-auth' });
  assert.equal('accessToken' in info, false);
  assert.equal('refreshToken' in info, false);
});

test('grok-subscription 模板保持固定 Base URL 与专属适配器', () => {
  const template = templateById('grok-subscription');
  assert.equal(template.baseUrlEditable, false);
  assert.equal(template.fixedBaseUrl, 'https://api.x.ai/v1');
  assert.deepEqual(template.adapters, ['grok-images']);
  const draft = validateConnectionDraft({ name: 'Grok 订阅', template: 'grok-subscription', adapter: 'grok-images', model: 'grok-imagine-image' });
  assert.equal(draft.baseUrl, 'https://api.x.ai/v1');
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'grok-subscription', adapter: 'openai-images', model: 'm' }), /不允许/);
});

test('grokImagesAdapter：会话快照、n 原生单请求、b64/url 解析、参考图拒绝', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: Buffer.from('image').toString('base64') }, { url: 'https://imgen.x.ai/x.jpeg' }] }) };
  };
  const assets = await grokImagesAdapter({
    endpoint: 'https://api.x.ai/v1', model: 'grok-imagine-image', credential: JSON.stringify({ access: 'access-live' }),
    request: { prompt: '绘制模型结构图', count: 2 }, references: [], fetchImpl,
  });
  assert.equal(calls.length, 1);
  assert.equal(assets.length, 2);
  assert.equal(calls[0].init.headers.authorization, 'Bearer access-live');
  await assert.rejects(
    () => grokImagesAdapter({ credential: '{}', request: { prompt: 'p', count: 1 }, references: [{}], fetchImpl }),
    /不支持参考图/,
  );
});

test('grokImagesAdapter：401 仅通过同一 service 强刷一次后重试', async () => {
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-rotated' }] });
  let imageCalls = 0;
  const headers = [];
  const fetchImpl = async (_url, init) => {
    imageCalls += 1;
    headers.push(init.headers.authorization);
    if (imageCalls === 1) return { ok: false, status: 401, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: Buffer.from('image').toString('base64') }] }) };
  };
  const assets = await grokImagesAdapter({
    credential: JSON.stringify({ access: 'access-stale' }), request: { prompt: 'p', count: 1 }, references: [],
    fetchImpl, subscriptionSessions,
  });
  assert.equal(assets.length, 1);
  assert.deepEqual(headers, ['Bearer access-stale', 'Bearer access-rotated']);
  assert.deepEqual(subscriptionSessions.calls.map((call) => [call.method, call.provider, call.options?.force]), [['resolve', 'grok', true]]);
});

test('grokImagesAdapter：连续 401 不发生第二次刷新或无限重试', async () => {
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-rotated' }] });
  let imageCalls = 0;
  await assert.rejects(
    () => grokImagesAdapter({
      credential: JSON.stringify({ access: 'access-stale' }), request: { prompt: 'p', count: 1 }, references: [],
      subscriptionSessions,
      fetchImpl: async () => { imageCalls += 1; return { ok: false, status: 401, json: async () => ({}) }; },
    }),
    /HTTP 401/,
  );
  assert.equal(imageCalls, 2);
  assert.equal(subscriptionSessions.calls.filter((call) => call.method === 'resolve').length, 1);
});
