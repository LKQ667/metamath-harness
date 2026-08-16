import { safeError } from './security/redact.js';

const LISTABLE_PROTOCOLS = new Set(['openai-completions', 'openai-responses']);

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function listingUrl(baseURL) {
  let parsed;
  try { parsed = new URL(baseURL); }
  catch { throw fail('invalid_base_url', '该供应商的 API 地址无效，无法获取模型列表'); }
  if (!['https:', 'http:'].includes(parsed.protocol)) throw fail('invalid_base_url', '该供应商的 API 地址必须使用 HTTP 或 HTTPS');
  return `${baseURL.replace(/\/+$/, '')}/models`;
}

function readModels(payload) {
  if (!Array.isArray(payload?.data)) throw fail('invalid_models_response', '模型列表接口未返回 data 数组；请手动添加模型');
  const seen = new Set();
  const models = [];
  for (const entry of payload.data) {
    const id = typeof entry?.id === 'string' ? entry.id.trim() : '';
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const name = typeof entry?.name === 'string' && entry.name.trim()
      ? entry.name.trim()
      : typeof entry?.display_name === 'string' && entry.display_name.trim()
        ? entry.display_name.trim()
        : undefined;
    models.push(Object.freeze({ id, ...(name ? { name } : {}) }));
  }
  return Object.freeze(models);
}

/**
 * 只从已保存的供应商配置取得目标地址和凭据；浏览器既不能传入 Key，
 * 也不能借此服务请求任意 URL。
 */
export class StoredKeyModelDiscoveryService {
  constructor({ settings, credentials, fetchImpl = globalThis.fetch } = {}) {
    this.settings = settings;
    this.credentials = credentials;
    this.fetch = fetchImpl;
  }

  async discover(provider, { signal } = {}) {
    const route = typeof provider === 'string' ? provider.trim() : '';
    if (!/^[a-z0-9][a-z0-9-]*$/.test(route)) throw fail('invalid_provider', '供应商标识无效');
    const profile = this.settings.get('llm-pi-ai')?.providers?.[route];
    if (!profile || typeof profile !== 'object') throw fail('provider_not_found', '未找到该已配置供应商');
    if (!LISTABLE_PROTOCOLS.has(profile.api ?? 'openai-completions')) throw fail('discovery_unsupported', '该 API 协议不支持自动获取模型，请手动添加模型');
    if (typeof profile.baseURL !== 'string' || !profile.baseURL.trim()) throw fail('invalid_base_url', '请先填写该供应商的 API 地址');
    if (typeof profile.apiKeyEnv !== 'string' || !profile.apiKeyEnv.trim()) throw fail('credential_missing', '该供应商未关联受管 API Key；请先保存 API Key');

    const credential = await this.credentials.resolve(profile.apiKeyEnv);
    const secret = typeof credential?.value === 'string' ? credential.value.trim() : '';
    if (!secret) throw fail('credential_missing', '未找到该供应商已保存的 API Key；请重新保存后再获取模型');
    const url = listingUrl(profile.baseURL.trim());
    try {
      const response = await this.fetch(url, {
        method: 'GET',
        headers: { accept: 'application/json', authorization: `Bearer ${secret}` },
        ...(signal ? { signal } : {}),
      });
      if (!response?.ok) {
        const status = response?.status ?? '未知';
        if (status === 401 || status === 403) throw fail('models_endpoint_rejected', `模型列表接口拒绝了请求（HTTP ${status}）；模型仍可手动添加，且这不等同于聊天模型不可用`);
        throw fail('models_http_error', `模型列表接口请求失败（HTTP ${status}）`);
      }
      return Object.freeze({ provider: route, models: readModels(await response.json()) });
    } catch (error) {
      if (signal?.aborted) throw fail('cancelled', '获取模型已取消');
      const cleaned = safeError(error, [secret]);
      if (typeof error?.code === 'string') cleaned.code = error.code;
      throw cleaned;
    }
  }
}

export { readModels as parseStoredKeyModels };
