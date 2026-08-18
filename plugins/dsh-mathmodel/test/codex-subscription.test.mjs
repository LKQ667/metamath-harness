import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  CODEX_CREDENTIAL_KEY, accountIdFromAccessToken, codexAuthPath, describeCodexCredential,
  readCodexCredential, refreshCodexCredential, resolveCodexSession, writeCodexCredential,
} from '../src/image/codex-auth.js';
import { codexImagesAdapter } from '../src/image/adapters.js';
import { templateById, validateConnectionDraft } from '../src/security/image-connections.js';

// 用无效签名但结构正确的 JWT 携带 claims（解码路径不验签，与 pi-ai 同信任姿态）。
function fakeJwt({ accountId = 'acct_123', exp = 4_102_444_800 } = {}) {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ exp, 'https://api.openai.com/auth': { chatgpt_account_id: accountId } })).toString('base64url');
  return `${header}.${payload}.sig`;
}

function credential({ access = 'access-old', refresh = 'refresh-old', expires = 0, accountId = 'acct_123' } = {}) {
  return { type: 'oauth', access, refresh, expires, accountId };
}

async function homeWith(credentialValue) {
  const home = await mkdtemp(join(tmpdir(), 'dsh-codex-'));
  if (credentialValue !== undefined) {
    await writeFile(codexAuthPath(home), `${JSON.stringify({ [CODEX_CREDENTIAL_KEY]: credentialValue })}\n`);
  }
  return home;
}

const tokenResponse = ({ accessToken = 'access-new', refreshToken = 'refresh-new', expiresIn = 3600 } = {}) => ({
  ok: true, status: 200, json: async () => ({ access_token: accessToken, refresh_token: refreshToken, expires_in: expiresIn }),
});

test('accountIdFromAccessToken 从 JWT 解出 chatgpt account id', () => {
  assert.equal(accountIdFromAccessToken(fakeJwt({ accountId: 'acct_xyz' })), 'acct_xyz');
  assert.equal(accountIdFromAccessToken('not-a-jwt'), undefined);
  assert.equal(accountIdFromAccessToken(fakeJwt({ accountId: '' })), undefined);
});

test('readCodexCredential：缺失文件与非 OAuth 条目返回 undefined', async () => {
  const empty = await homeWith(undefined);
  assert.equal(await readCodexCredential(empty), undefined);
  const bad = await homeWith({ type: 'api_key', key: 'k' });
  assert.equal(await readCodexCredential(bad), undefined);
  const good = await homeWith(credential());
  assert.deepEqual(await readCodexCredential(good), credential());
});

test('writeCodexCredential 仅替换 openai-codex 条目并保留其他登录', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-codex-'));
  await writeFile(codexAuthPath(home), `${JSON.stringify({ 'anthropic': credential({ access: 'keep-me' }), [CODEX_CREDENTIAL_KEY]: credential() })}\n`);
  await writeCodexCredential(credential({ access: 'access-2' }), home);
  const parsed = JSON.parse(await readFile(codexAuthPath(home), 'utf8'));
  assert.equal(parsed.anthropic.access, 'keep-me');
  assert.equal(parsed[CODEX_CREDENTIAL_KEY].access, 'access-2');
  // 空目录也能写（自动建目录）
  const fresh = join(home, 'nested', 'home');
  await writeCodexCredential(credential(), fresh);
  assert.equal((await readCodexCredential(fresh)).access, 'access-old');
});

test('refreshCodexCredential：form-encoded grant、新 accountId、旧值兜底', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return tokenResponse({ accessToken: fakeJwt({ accountId: 'acct_fresh' }) });
  };
  const next = await refreshCodexCredential(credential(), { fetchImpl });
  assert.equal(calls[0].url, 'https://auth.openai.com/oauth/token');
  assert.equal(calls[0].init.headers['content-type'], 'application/x-www-form-urlencoded');
  const params = new URLSearchParams(calls[0].init.body);
  assert.equal(params.get('grant_type'), 'refresh_token');
  assert.equal(params.get('client_id'), 'app_EMoamEEZ73f0CkXaXp7hrann');
  assert.equal(params.get('refresh_token'), 'refresh-old');
  assert.equal(next.access, fakeJwt({ accountId: 'acct_fresh' }));
  assert.equal(next.accountId, 'acct_fresh');
  assert.equal(next.type, 'oauth');
  // 新 token 解不出 accountId 时沿用旧值
  const fallback = await refreshCodexCredential(credential({ accountId: 'acct_keep' }), {
    fetchImpl: async () => tokenResponse({ accessToken: 'opaque-opaque-opaque' }),
  });
  assert.equal(fallback.accountId, 'acct_keep');
});

test('refreshCodexCredential：拒绝与坏响应的错误分类', async () => {
  await assert.rejects(
    () => refreshCodexCredential(credential(), { fetchImpl: async () => ({ ok: false, status: 400, json: async () => ({ error: 'invalid_grant' }) }) }),
    (error) => error.code === 'codex_refresh_rejected' && /重新登录/.test(error.message),
  );
  await assert.rejects(
    () => refreshCodexCredential(credential(), { fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ access_token: 'a', expires_in: 3600 }) }) }),
    (error) => error.code === 'codex_refresh_invalid',
  );
});

test('resolveCodexSession：未登录、有效期内直用、临期刷新并写回', async () => {
  const missing = await homeWith(undefined);
  await assert.rejects(() => resolveCodexSession({ home: missing }), (error) => error.code === 'credential_missing');

  const fresh = await homeWith(credential({ expires: Date.now() + 60 * 60_000 }));
  const direct = await resolveCodexSession({ home: fresh });
  assert.equal(direct.accessToken, 'access-old');
  assert.equal(direct.accountId, 'acct_123');

  const stale = await homeWith(credential({ expires: Date.now() + 60_000 }));
  const refreshed = await resolveCodexSession({
    home: stale,
    fetchImpl: async () => tokenResponse({ accessToken: fakeJwt({ accountId: 'acct_new' }) }),
  });
  assert.equal(refreshed.accountId, 'acct_new');
  const stored = await readCodexCredential(stale);
  assert.equal(stored.access, fakeJwt({ accountId: 'acct_new' }));
  assert.equal(stored.refresh, 'refresh-new');
});

test('describeCodexCredential：登录状态布尔且不含秘密', async () => {
  const missing = await homeWith(undefined);
  assert.deepEqual(await describeCodexCredential(missing), { ref: 'pi-ai-oauth', configured: false, writable: false, source: 'pi-ai-oauth' });
  const good = await homeWith(credential());
  const info = await describeCodexCredential(good);
  assert.equal(info.configured, true);
  assert.equal('access' in info, false);
  // 坏 JSON 不抛错，视为未登录
  const broken = await mkdtemp(join(tmpdir(), 'dsh-codex-'));
  await mkdir(broken, { recursive: true });
  await writeFile(codexAuthPath(broken), 'not-json');
  assert.equal((await describeCodexCredential(broken)).configured, false);
});

test('codex-subscription 模板：固定 Base URL、专属适配器、草稿校验', () => {
  const template = templateById('codex-subscription');
  assert.equal(template.baseUrlEditable, false);
  assert.equal(template.fixedBaseUrl, 'https://chatgpt.com/backend-api');
  assert.deepEqual(template.adapters, ['codex-images']);
  const draft = validateConnectionDraft({ name: 'ChatGPT 订阅', template: 'codex-subscription', adapter: 'codex-images', model: 'gpt-image-2' });
  assert.equal(draft.baseUrl, 'https://chatgpt.com/backend-api');
  // 试图改 Base URL 或换适配器都会被拒
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'codex-subscription', adapter: 'codex-images', model: 'm', baseUrl: 'https://evil.example' }), /固定|fixed/i);
  assert.throws(() => validateConnectionDraft({ name: 'x', template: 'codex-subscription', adapter: 'openai-images', model: 'm' }), /不允许/);
});

test('codexImagesAdapter：会话快照请求头、b64 解析、count 循环、参考图拒绝', async () => {
  const calls = [];
  const b64 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) };
  };
  const credentialJson = JSON.stringify({ access: 'access-live', accountId: 'acct_9' });
  const assets = await codexImagesAdapter({
    endpoint: 'https://chatgpt.com/backend-api', model: 'gpt-image-2', credential: credentialJson,
    request: { prompt: '绘制模型结构图', count: 2 }, references: [], fetchImpl,
  });
  assert.equal(assets.length, 2);
  assert.equal(assets[0].kind, 'base64');
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, 'https://chatgpt.com/backend-api/codex/images/generations');
  assert.equal(calls[0].init.headers.authorization, 'Bearer access-live');
  assert.equal(calls[0].init.headers['chatgpt-account-id'], 'acct_9');
  assert.equal(calls[0].init.headers.originator, 'codex_cli_rs');
  assert.equal(JSON.parse(calls[0].init.body).model, 'gpt-image-2');
  // 参考图明确拒绝
  await assert.rejects(
    () => codexImagesAdapter({ credential: credentialJson, request: { prompt: 'p', count: 1 }, references: [{}], fetchImpl }),
    /不支持参考图/,
  );
});

test('codexImagesAdapter：401 强刷一次后重试成功', async () => {
  const b64 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
  const home = await homeWith(credential({ expires: Date.now() + 60 * 60_000, access: 'access-stale' }));
  let imageCalls = 0;
  const fetchImpl = async (url) => {
    if (String(url).startsWith('https://auth.openai.com/')) {
      return { ok: true, status: 200, json: async () => ({ access_token: 'access-rotated', refresh_token: 'refresh-rotated', expires_in: 3600 }) };
    }
    imageCalls += 1;
    if (imageCalls === 1) return { ok: false, status: 401, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ data: [{ b64_json: b64 }] }) };
  };
  const assets = await codexImagesAdapter({
    credential: JSON.stringify({ access: 'access-stale', accountId: 'acct_9' }),
    request: { prompt: 'p', count: 1 }, references: [], fetchImpl, codexHome: home,
  });
  assert.equal(assets.length, 1);
  assert.equal(imageCalls, 2);
  const stored = await readCodexCredential(home);
  assert.equal(stored.access, 'access-rotated');
  assert.equal(stored.refresh, 'refresh-rotated');
});
