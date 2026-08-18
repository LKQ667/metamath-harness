import { homedir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fail } from '../security/image-connections.js';

/** pi-ai(dsh-llm-oauth) 的 openai-codex 凭据条目键。 */
export const CODEX_CREDENTIAL_KEY = 'openai-codex';
/** Codex CLI 公开 OAuth client id（与 pi-ai / codex-rs 一致）。 */
export const CODEX_CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann';
/** OAuth token 端点。 */
export const CODEX_TOKEN_URL = 'https://auth.openai.com/oauth/token';
/** access token 剩余寿命低于该值时预刷新。 */
export const CODEX_PREEMPT_MS = 5 * 60_000;

/** 与 dsh-llm-oauth home.ts 相同的 DSH_HOME 解析（env 优先，默认 ~/.dsh）。 */
export function resolveDshHome(env = process.env) {
  const fromEnv = env.DSH_HOME;
  const selected = fromEnv !== undefined && fromEnv.trim().length > 0 ? fromEnv : join(homedir(), '.dsh');
  return resolve(selected);
}

/** pi-ai OAuth 凭据文件的默认路径。 */
export function codexAuthPath(home = resolveDshHome()) {
  return join(home, 'pi-ai-oauth.json');
}

function decodeJwtPayload(token) {
  try {
    const payload = String(token).split('.')[1] ?? '';
    return JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
  } catch {
    return undefined;
  }
}

/** 从 access token JWT 解 chatgpt_account_id（与 pi-ai codex 流程一致）。 */
export function accountIdFromAccessToken(accessToken) {
  const payload = decodeJwtPayload(accessToken);
  const auth = payload?.['https://api.openai.com/auth'];
  const accountId = auth?.chatgpt_account_id;
  return typeof accountId === 'string' && accountId.length > 0 ? accountId : undefined;
}

function asOAuthCredential(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return undefined;
  if (value.type !== 'oauth' || typeof value.access !== 'string' || typeof value.refresh !== 'string') return undefined;
  return value;
}

/** 读取 openai-codex 凭据（可能已过期）；文件或条目缺失返回 undefined。 */
export async function readCodexCredential(home = resolveDshHome()) {
  let parsed;
  try {
    parsed = JSON.parse(await readFile(codexAuthPath(home), 'utf8'));
  } catch (error) {
    if (error?.code === 'ENOENT') return undefined;
    throw fail('codex_auth_unreadable', `订阅凭据文件无法读取：${error?.message ?? error}`);
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return undefined;
  return asOAuthCredential(parsed[CODEX_CREDENTIAL_KEY]);
}

/** 读-改-写全文件：仅替换 openai-codex 条目，保留其他 provider 的登录状态。 */
export async function writeCodexCredential(credential, home = resolveDshHome()) {
  const path = codexAuthPath(home);
  let parsed = {};
  try {
    parsed = JSON.parse(await readFile(path, 'utf8'));
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) parsed = {};
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  parsed[CODEX_CREDENTIAL_KEY] = credential;
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(parsed, null, 2)}\n`, 'utf8');
}

/**
 * 刷新 Codex OAuth 凭据（form-encoded refresh grant，与 pi-ai 实现一致）。
 * 响应必须携带 access_token/refresh_token/expires_in；accountId 从新 token 解出，解不出沿用旧值。
 */
export async function refreshCodexCredential(credential, { fetchImpl = globalThis.fetch, signal } = {}) {
  const response = await fetchImpl(CODEX_TOKEN_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: credential.refresh,
      client_id: CODEX_CLIENT_ID,
    }).toString(),
    signal,
  });
  if (!response.ok) {
    let detail = '';
    try { detail = JSON.stringify((await response.json())?.error ?? ''); } catch { /* 非 JSON 错误体 */ }
    throw fail('codex_refresh_rejected', `订阅 token 刷新被拒绝（HTTP ${response.status}${detail ? `：${detail}` : ''}）；请重新登录 ChatGPT 订阅`);
  }
  const payload = await response.json();
  if (typeof payload?.access_token !== 'string' || typeof payload?.refresh_token !== 'string' || typeof payload?.expires_in !== 'number') {
    throw fail('codex_refresh_invalid', '订阅 token 刷新响应缺少必要字段；请重新登录 ChatGPT 订阅');
  }
  const accountId = accountIdFromAccessToken(payload.access_token) ?? credential.accountId;
  if (typeof accountId !== 'string' || accountId.length === 0) {
    throw fail('codex_refresh_invalid', '订阅凭据缺少 chatgpt account id；请重新登录 ChatGPT 订阅');
  }
  return {
    type: 'oauth',
    access: payload.access_token,
    refresh: payload.refresh_token,
    expires: Date.now() + payload.expires_in * 1000,
    accountId,
  };
}

/**
 * 解析可用的 Codex 会话：读取凭据，剩余寿命不足（或 force）时刷新并写回。
 * @returns {{accessToken: string, accountId: string}}
 */
export async function resolveCodexSession({ home = resolveDshHome(), fetchImpl = globalThis.fetch, preemptMs = CODEX_PREEMPT_MS, force = false, signal } = {}) {
  const credential = await readCodexCredential(home);
  if (credential === undefined) {
    throw fail('credential_missing', '尚未登录 ChatGPT 订阅；请先在“设置 → OAuth / 订阅”完成 openai-codex 登录');
  }
  let current = credential;
  if (force || typeof current.expires !== 'number' || current.expires - Date.now() < preemptMs) {
    current = await refreshCodexCredential(current, { fetchImpl, signal });
    await writeCodexCredential(current, home);
  }
  return { accessToken: current.access, accountId: current.accountId };
}

/** 登录状态描述（不含秘密）：configured 为凭据文件存在 openai-codex OAuth 条目。 */
export async function describeCodexCredential(home = resolveDshHome()) {
  const credential = await readCodexCredential(home).catch(() => undefined);
  return Object.freeze({ ref: 'pi-ai-oauth', configured: credential !== undefined, writable: false, source: 'pi-ai-oauth' });
}
