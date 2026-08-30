import test from 'node:test';
import assert from 'node:assert/strict';
import { describeCodexCredential, resolveCodexSession } from '../src/image/codex-auth.js';
import { codexImagesAdapter } from '../src/image/adapters.js';
import { templateById, validateConnectionDraft } from '../src/security/image-connections.js';

function service({ configured = true, sessions = [] } = {}) {
  const calls = [];
  return {
    calls,
    async describe(provider) {
      calls.push({ method: 'describe', provider });
      return { configured };
    },
    async resolve(provider, options) {
      calls.push({ method: 'resolve', provider, options });
      const next = sessions.shift() ?? { accessToken: 'access-live', accountId: 'acct_9' };
      return next;
    },
  };
}

test('resolveCodexSession：只通过 Host service 解析且不暴露 refresh token', async () => {
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-live', accountId: 'acct_9', refreshToken: 'never-forward' }] });
  const result = await resolveCodexSession({ subscriptionSessions, force: true });
  assert.deepEqual(result, { accessToken: 'access-live', accountId: 'acct_9' });
  assert.equal('refreshToken' in result, false);
  assert.equal(subscriptionSessions.calls.length, 1);
  assert.equal(subscriptionSessions.calls[0].provider, 'codex');
  assert.equal(subscriptionSessions.calls[0].options.force, true);
});

test('resolveCodexSession：服务缺失与坏会话失败关闭', async () => {
  await assert.rejects(
    () => resolveCodexSession(),
    (error) => error.code === 'subscription_service_unavailable' && /订阅插件/.test(error.message),
  );
  await assert.rejects(
    () => resolveCodexSession({ subscriptionSessions: service({ sessions: [{ accessToken: 'a' }] }) }),
    (error) => error.code === 'subscription_session_invalid',
  );
});

test('describeCodexCredential：仅返回脱敏状态，服务缺失视为未就绪', async () => {
  assert.deepEqual(await describeCodexCredential(), {
    ref: 'subscriptions-auth', configured: false, writable: false, source: 'subscriptions-auth',
  });
  const subscriptionSessions = service({ configured: true });
  const info = await describeCodexCredential(subscriptionSessions);
  assert.deepEqual(info, { ref: 'subscriptions-auth', configured: true, writable: false, source: 'subscriptions-auth' });
  assert.equal('accessToken' in info, false);
  assert.equal('refreshToken' in info, false);
});

test('codex-subscription 模板保持固定 Base URL 与专属适配器', () => {
  const template = templateById('codex-subscription');
  assert.equal(template.baseUrlEditable, false);
  assert.equal(template.fixedBaseUrl, 'https://chatgpt.com/backend-api');
  assert.deepEqual(template.adapters, ['codex-images']);
  const draft = validateConnectionDraft({ name: 'ChatGPT 订阅', template: 'codex-subscription', adapter: 'codex-images', model: 'gpt-image-2' });
  assert.equal(draft.baseUrl, 'https://chatgpt.com/backend-api');
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'codex-subscription', adapter: 'openai-images', model: 'm' }), /不允许/);
});

test('codexImagesAdapter：会话快照请求头、b64 解析、count 循环、参考图拒绝', async () => {
  const calls = [];
  const b64 = Buffer.from('image').toString('base64');
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) };
  };
  const assets = await codexImagesAdapter({
    endpoint: 'https://chatgpt.com/backend-api', model: 'gpt-image-2',
    credential: JSON.stringify({ access: 'access-live', accountId: 'acct_9' }),
    request: { prompt: '绘制模型结构图', count: 2 }, references: [], fetchImpl,
  });
  assert.equal(assets.length, 2);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, 'https://chatgpt.com/backend-api/codex/images/generations');
  assert.equal(calls[0].init.headers.authorization, 'Bearer access-live');
  assert.equal(calls[0].init.headers['chatgpt-account-id'], 'acct_9');
  await assert.rejects(
    () => codexImagesAdapter({ credential: '{}', request: { prompt: 'p', count: 1 }, references: [{}], fetchImpl }),
    /不支持参考图/,
  );
});

test('codexImagesAdapter：401 仅通过同一 service 强刷一次后重试', async () => {
  const b64 = Buffer.from('image').toString('base64');
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-rotated', accountId: 'acct_9' }] });
  let imageCalls = 0;
  const headers = [];
  const fetchImpl = async (_url, init) => {
    imageCalls += 1;
    headers.push(init.headers.authorization);
    if (imageCalls === 1) return { ok: false, status: 401, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) };
  };
  const assets = await codexImagesAdapter({
    credential: JSON.stringify({ access: 'access-stale', accountId: 'acct_9' }),
    request: { prompt: 'p', count: 1 }, references: [], fetchImpl, subscriptionSessions,
  });
  assert.equal(assets.length, 1);
  assert.deepEqual(headers, ['Bearer access-stale', 'Bearer access-rotated']);
  assert.deepEqual(subscriptionSessions.calls.map((call) => [call.method, call.provider, call.options?.force]), [['resolve', 'codex', true]]);
});

test('codexImagesAdapter：连续 401 不发生第二次刷新或无限重试', async () => {
  const subscriptionSessions = service({ sessions: [{ accessToken: 'access-rotated', accountId: 'acct_9' }] });
  let imageCalls = 0;
  await assert.rejects(
    () => codexImagesAdapter({
      credential: JSON.stringify({ access: 'access-stale', accountId: 'acct_9' }),
      request: { prompt: 'p', count: 1 }, references: [], subscriptionSessions,
      fetchImpl: async () => { imageCalls += 1; return { ok: false, status: 401, json: async () => ({}) }; },
    }),
    /HTTP 401/,
  );
  assert.equal(imageCalls, 2);
  assert.equal(subscriptionSessions.calls.filter((call) => call.method === 'resolve').length, 1);
});
