import { homedir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fail } from '../security/image-connections.js';

/** dsh-plugin-subscriptions 的 grok 会话条目键（auth.json 顶层键）。 */
export const GROK_CREDENTIAL_KEY = 'grok';
/** Grok CLI 公开 OAuth client id（与 dsh-plugin-subscriptions 一致）。 */
export const GROK_CLIENT_ID = 'b1a00492-073a-47ea-816f-4c329264a828';
/** access token 剩余寿命低于该值时预刷新（与插件 GROK_PREEMPT_MS 一致）。 */
export const GROK_PREEMPT_MS = 2 * 60_000;

/** 与 dsh-plugin-subscriptions home 解析一致：env DSH_HOME 优先，默认 ~/.dsh。 */
export function resolveDshHome(env = process.env) {
  const fromEnv = env.DSH_HOME;
  const selected = fromEnv !== undefined && fromEnv.trim().length > 0 ? fromEnv : join(homedir(), '.dsh');
  return resolve(selected);
}

/** 订阅插件凭据文件的默认路径（plugins/subscriptions/auth.json）。 */
export function grokAuthPath(home = resolveDshHome()) {
  return join(home, 'plugins', 'subscriptions', 'auth.json');
}

function asGrokSession(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return undefined;
  if (typeof value.accessToken !== 'string' || value.accessToken.length === 0
    || typeof value.refreshToken !== 'string' || value.refreshToken.length === 0
    || typeof value.expiresAt !== 'number' || !Number.isFinite(value.expiresAt)
    || typeof value.tokenEndpoint !== 'string' || value.tokenEndpoint.length === 0) return undefined;
  return value;
}

/** 读取 grok 会话（可能已过期）；文件或条目缺失/形状不符返回 undefined。 */
export async function readGrokSession(home = resolveDshHome()) {
  let parsed;
  try {
    parsed = JSON.parse(await readFile(grokAuthPath(home), 'utf8'));
  } catch (error) {
    if (error?.code === 'ENOENT') return undefined;
    throw fail('grok_auth_unreadable', `订阅凭据文件无法读取：${error?.message ?? error}`);
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return undefined;
  return asGrokSession(parsed[GROK_CREDENTIAL_KEY]);
}

/** 读-改-写全文件：仅替换 grok 条目，保留其他 provider（codex/claude）的登录状态。 */
export async function writeGrokSession(session, home = resolveDshHome()) {
  const path = grokAuthPath(home);
  let parsed = {};
  try {
    parsed = JSON.parse(await readFile(path, 'utf8'));
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) parsed = {};
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  parsed[GROK_CREDENTIAL_KEY] = session;
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(parsed, null, 2)}\n`, 'utf8');
}

/**
 * 刷新 grok OAuth 会话（form-encoded refresh grant，与 dsh-plugin-subscriptions refreshGrok 一致）。
 * 响应必须携带 access_token 与正数 expires_in；refresh_token 缺失时沿用旧值；
 * scopes/account 保留旧会话的值（与插件 grokSession 的兜底语义一致）。
 */
export async function refreshGrokSession(session, { fetchImpl = globalThis.fetch, signal } = {}) {
  const response = await fetchImpl(session.tokenEndpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: GROK_CLIENT_ID,
      refresh_token: session.refreshToken,
    }).toString(),
    signal,
  });
  if (!response.ok) {
    let detail = '';
    try { detail = JSON.stringify((await response.json())?.error ?? ''); } catch { /* 非 JSON 错误体 */ }
    throw fail('grok_refresh_rejected', `订阅 token 刷新被拒绝（HTTP ${response.status}${detail ? `：${detail}` : ''}）；请重新登录 Grok 订阅`);
  }
  const payload = await response.json();
  if (typeof payload?.access_token !== 'string' || payload.access_token.length === 0
    || typeof payload?.expires_in !== 'number' || payload.expires_in <= 0) {
    throw fail('grok_refresh_invalid', '订阅 token 刷新响应缺少必要字段；请重新登录 Grok 订阅');
  }
  const refreshToken = typeof payload.refresh_token === 'string' && payload.refresh_token.length > 0
    ? payload.refresh_token
    : session.refreshToken;
  return {
    accessToken: payload.access_token,
    refreshToken,
    expiresAt: Date.now() + payload.expires_in * 1000,
    tokenEndpoint: session.tokenEndpoint,
    ...(typeof session.scopes === 'string' ? { scopes: session.scopes } : {}),
    ...(typeof session.account === 'string' ? { account: session.account } : {}),
  };
}

/**
 * 解析可用的 grok 会话：读取凭据，剩余寿命不足（或 force）时刷新并写回。
 * @returns {{accessToken: string}}
 */
export async function resolveGrokSession({ home = resolveDshHome(), fetchImpl = globalThis.fetch, preemptMs = GROK_PREEMPT_MS, force = false, signal } = {}) {
  const session = await readGrokSession(home);
  if (session === undefined) {
    throw fail('credential_missing', '尚未登录 Grok 订阅；请先在“设置 → 订阅”完成 Grok 登录');
  }
  let current = session;
  if (force || current.expiresAt - Date.now() < preemptMs) {
    current = await refreshGrokSession(current, { fetchImpl, signal });
    await writeGrokSession(current, home);
  }
  return { accessToken: current.accessToken };
}

/** 登录状态描述（不含秘密）：configured 为凭据文件存在 grok 会话条目。 */
export async function describeGrokCredential(home = resolveDshHome()) {
  const session = await readGrokSession(home).catch(() => undefined);
  return Object.freeze({ ref: 'subscriptions-auth', configured: session !== undefined, writable: false, source: 'subscriptions-auth' });
}
