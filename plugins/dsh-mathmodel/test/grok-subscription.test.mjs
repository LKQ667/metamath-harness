import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  GROK_CREDENTIAL_KEY, describeGrokCredential, grokAuthPath, readGrokSession,
  refreshGrokSession, resolveGrokSession, writeGrokSession,
} from '../src/image/grok-auth.js';
import { grokImagesAdapter } from '../src/image/adapters.js';
import { templateById, validateConnectionDraft } from '../src/security/image-connections.js';

// dsh-plugin-subscriptions 的 grok 会话形状（auth.json 顶层 grok 条目）
function session({ access = 'access-old', refresh = 'refresh-old', expiresAt = 0, tokenEndpoint = 'https://auth.x.ai/oauth2/token' } = {}) {
  return { accessToken: access, refreshToken: refresh, expiresAt, tokenEndpoint, scopes: 'openid profile email', account: 'user@example.com' };
}

async function homeWith(sessionValue) {
  const home = await mkdtemp(join(tmpdir(), 'dsh-grok-'));
  if (sessionValue !== undefined) {
    await mkdir(join(home, 'plugins', 'subscriptions'), { recursive: true });
    await writeFile(grokAuthPath(home), `${JSON.stringify({ [GROK_CREDENTIAL_KEY]: sessionValue })}\n`);
  }
  return home;
}

const tokenResponse = ({ accessToken = 'access-new', refreshToken = 'refresh-new', expiresIn = 3600 } = {}) => ({
  ok: true, status: 200, json: async () => ({ access_token: accessToken, refresh_token: refreshToken, expires_in: expiresIn }),
});

test('readGrokSession：缺失文件与形状不符条目返回 undefined', async () => {
  const empty = await homeWith(undefined);
  assert.equal(await readGrokSession(empty), undefined);
  const bad = await homeWith({ accessToken: 'a' });
  assert.equal(await readGrokSession(bad), undefined);
  const good = await homeWith(session());
  assert.deepEqual(await readGrokSession(good), session());
});

test('writeGrokSession 仅替换 grok 条目并保留其他 provider 登录', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-grok-'));
  await mkdir(join(home, 'plugins', 'subscriptions'), { recursive: true });
  await writeFile(grokAuthPath(home), `${JSON.stringify({ codex: { keep: true }, [GROK_CREDENTIAL_KEY]: session() })}\n`);
  await writeGrokSession(session({ access: 'access-2' }), home);
  const parsed = JSON.parse(await readFile(grokAuthPath(home), 'utf8'));
  assert.equal(parsed.codex.keep, true);
  assert.equal(parsed[GROK_CREDENTIAL_KEY].accessToken, 'access-2');
  // 空目录也能写（自动建目录）
  const fresh = join(home, 'nested', 'home');
  await writeGrokSession(session(), fresh);
  assert.equal((await readGrokSession(fresh)).accessToken, 'access-old');
});

test('refreshGrokSession：form-encoded grant、refresh_token 兜底、scopes/account 保留', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    // 响应完全不带 refresh_token 字段（插件同款兜底语义）
    return { ok: true, status: 200, json: async () => ({ access_token: 'access-new', expires_in: 3600 }) };
  };
  const next = await refreshGrokSession(session(), { fetchImpl });
  assert.equal(calls[0].url, 'https://auth.x.ai/oauth2/token');
  assert.equal(calls[0].init.headers['content-type'], 'application/x-www-form-urlencoded');
  const params = new URLSearchParams(calls[0].init.body);
  assert.equal(params.get('grant_type'), 'refresh_token');
  assert.equal(params.get('client_id'), 'b1a00492-073a-47ea-816f-4c329264a828');
  assert.equal(params.get('refresh_token'), 'refresh-old');
  assert.equal(next.accessToken, 'access-new');
  // 响应缺 refresh_token 时沿用旧值；scopes/account 保留旧会话
  assert.equal(next.refreshToken, 'refresh-old');
  assert.equal(next.scopes, 'openid profile email');
  assert.equal(next.account, 'user@example.com');
});

test('refreshGrokSession：拒绝与坏响应的错误分类', async () => {
  await assert.rejects(
    () => refreshGrokSession(session(), { fetchImpl: async () => ({ ok: false, status: 400, json: async () => ({ error: 'invalid_grant' }) }) }),
    (error) => error.code === 'grok_refresh_rejected' && /重新登录/.test(error.message),
  );
  await assert.rejects(
    () => refreshGrokSession(session(), { fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ access_token: 'a', expires_in: 0 }) }) }),
    (error) => error.code === 'grok_refresh_invalid',
  );
});

test('resolveGrokSession：未登录、有效期内直用、临期刷新并写回', async () => {
  const missing = await homeWith(undefined);
  await assert.rejects(() => resolveGrokSession({ home: missing }), (error) => error.code === 'credential_missing');

  const fresh = await homeWith(session({ expiresAt: Date.now() + 60 * 60_000 }));
  const direct = await resolveGrokSession({ home: fresh });
  assert.equal(direct.accessToken, 'access-old');

  const stale = await homeWith(session({ expiresAt: Date.now() + 60_000 }));
  const refreshed = await resolveGrokSession({
    home: stale,
    fetchImpl: async () => tokenResponse({ accessToken: 'access-rotated', refreshToken: 'refresh-rotated' }),
  });
  assert.equal(refreshed.accessToken, 'access-rotated');
  const stored = await readGrokSession(stale);
  assert.equal(stored.accessToken, 'access-rotated');
  assert.equal(stored.refreshToken, 'refresh-rotated');
});

test('describeGrokCredential：登录状态布尔且不含秘密', async () => {
  const missing = await homeWith(undefined);
  assert.deepEqual(await describeGrokCredential(missing), { ref: 'subscriptions-auth', configured: false, writable: false, source: 'subscriptions-auth' });
  const good = await homeWith(session());
  const info = await describeGrokCredential(good);
  assert.equal(info.configured, true);
  assert.equal('accessToken' in info, false);
  // 坏 JSON 不抛错，视为未登录
  const broken = await mkdtemp(join(tmpdir(), 'dsh-grok-'));
  await mkdir(join(broken, 'plugins', 'subscriptions'), { recursive: true });
  await writeFile(grokAuthPath(broken), 'not-json');
  assert.equal((await describeGrokCredential(broken)).configured, false);
});

test('grok-subscription 模板：固定 Base URL、专属适配器、草稿校验', () => {
  const template = templateById('grok-subscription');
  assert.equal(template.baseUrlEditable, false);
  assert.equal(template.fixedBaseUrl, 'https://api.x.ai/v1');
  assert.deepEqual(template.adapters, ['grok-images']);
  const draft = validateConnectionDraft({ name: 'Grok 订阅', template: 'grok-subscription', adapter: 'grok-images', model: 'grok-imagine-image' });
  assert.equal(draft.baseUrl, 'https://api.x.ai/v1');
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'grok-subscription', adapter: 'grok-images', model: 'm', baseUrl: 'https://evil.example' }), /固定|fixed/i);
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'grok-subscription', adapter: 'openai-images', model: 'm' }), /不允许/);
});

test('grokImagesAdapter：会话快照、n 原生单请求、b64/url 解析、参考图拒绝', async () => {
  const calls = [];
  const b64 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }, { url: 'https://imgen.x.ai/x.jpeg', mime_type: 'image/jpeg' }] }) };
  };
  const credentialJson = JSON.stringify({ access: 'access-live' });
  const assets = await grokImagesAdapter({
    endpoint: 'https://api.x.ai/v1', model: 'grok-imagine-image', credential: credentialJson,
    request: { prompt: '绘制模型结构图', count: 2 }, references: [], fetchImpl,
  });
  // n 原生支持：一次请求返回多图，不做 count 循环
  assert.equal(calls.length, 1);
  assert.equal(assets.length, 2);
  assert.equal(assets[0].kind, 'base64');
  assert.equal(assets[1].kind, 'url');
  assert.equal(calls[0].url, 'https://api.x.ai/v1/images/generations');
  assert.equal(calls[0].init.headers.authorization, 'Bearer access-live');
  const body = JSON.parse(calls[0].init.body);
  assert.equal(body.model, 'grok-imagine-image');
  assert.equal(body.n, 2);
  assert.equal(body.response_format, 'b64_json');
  // 参考图明确拒绝
  await assert.rejects(
    () => grokImagesAdapter({ credential: credentialJson, request: { prompt: 'p', count: 1 }, references: [{}], fetchImpl }),
    /不支持参考图/,
  );
});

test('grokImagesAdapter：401 强刷一次后重试成功', async () => {
  const b64 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
  const home = await homeWith(session({ expiresAt: Date.now() + 60 * 60_000, access: 'access-stale' }));
  let imageCalls = 0;
  const imageHeaders = [];
  const fetchImpl = async (url, init) => {
    if (String(url).startsWith('https://auth.x.ai/')) {
      return { ok: true, status: 200, json: async () => ({ access_token: 'access-rotated', refresh_token: 'refresh-rotated', expires_in: 3600 }) };
    }
    imageCalls += 1;
    imageHeaders.push(init?.headers?.authorization);
    if (imageCalls === 1) return { ok: false, status: 401, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) };
  };
  const assets = await grokImagesAdapter({
    credential: JSON.stringify({ access: 'access-stale' }),
    request: { prompt: 'p', count: 1 }, references: [], fetchImpl, grokHome: home,
  });
  assert.equal(assets.length, 1);
  assert.equal(imageCalls, 2);
  // 重试必须携带刷新后的 token（防止 undefined token 的测试盲区）
  assert.equal(imageHeaders[0], 'Bearer access-stale');
  assert.equal(imageHeaders[1], 'Bearer access-rotated');
  const stored = await readGrokSession(home);
  assert.equal(stored.accessToken, 'access-rotated');
  assert.equal(stored.refreshToken, 'refresh-rotated');
});

test('grokImagesAdapter：凭据缺失时走 grok-auth 解析', async () => {
  const b64 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
  const home = await homeWith(session({ expiresAt: Date.now() + 60 * 60_000, access: 'access-direct' }));
  const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) });
  const assets = await grokImagesAdapter({
    model: 'grok-imagine-image', credential: 'not-json',
    request: { prompt: 'p', count: 1 }, references: [], fetchImpl, grokHome: home,
  });
  assert.equal(assets.length, 1);
});
