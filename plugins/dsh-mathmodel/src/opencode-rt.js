import Schema from '@deepseek-ai/schemastery';
import { safeError } from './security/redact.js';

export const OPENCODE_RT_PROVIDER = 'opencode-rt';
export const OPENCODE_RT_ENDPOINT = 'https://opencode.ai/zen/go/v1';
export const OPENCODE_RT_MODELS_ENDPOINT = `${OPENCODE_RT_ENDPOINT}/models`;
export const OPENCODE_RT_CREDENTIAL = 'OPENCODE_GO_API_KEY';

const CATALOG = Object.freeze([
  ['glm-5.3', 'GLM-5.3', false], ['glm-5.2', 'GLM-5.2', false], ['glm-5.1', 'GLM-5.1', false],
  ['kimi-k3', 'Kimi K3', true], ['kimi-k2.7-code', 'Kimi K2.7 Code', true], ['kimi-k2.6', 'Kimi K2.6', true],
  ['deepseek-v4-pro', 'DeepSeek V4 Pro', false], ['deepseek-v4-flash', 'DeepSeek V4 Flash', false],
  ['mimo-v2.5', 'MiMo-V2.5', true], ['mimo-v2.5-pro', 'MiMo-V2.5-Pro', false], ['hy3', 'Hy3', false],
].map(([id, name, visionSupported]) => Object.freeze({ id, name, visionSupported })));
const CATALOG_BY_ID = new Map(CATALOG.map((model) => [model.id, model]));
const TINY_PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9NwAAAABJRU5ErkJggg==';

export const OpenCodeRtSettingsSchema = Schema.object({
  verifiedVisionModels: Schema.array(Schema.string()).default([]).description('已通过最小识图验收的 OpenCode RT 模型'),
});

function fail(code, message) { const value = new Error(message); value.code = code; return value; }
function textOf(content) { return typeof content === 'string' ? content.trim() : Array.isArray(content) ? content.map((item) => typeof item?.text === 'string' ? item.text : '').join('').trim() : ''; }

export function parseOpenCodeModels(payload) {
  if (payload?.object !== 'list' || !Array.isArray(payload.data)) throw fail('invalid_models_response', 'OpenCode 模型接口返回格式无效');
  const ids = payload.data.map((entry) => entry?.id).filter((id) => typeof id === 'string' && id.trim()).map((id) => id.trim());
  if (new Set(ids).size !== ids.length) throw fail('invalid_models_response', 'OpenCode 模型接口返回了重复模型 ID');
  return Object.freeze(ids.sort());
}

export function buildOpenCodeRtProfile(ids, verifiedVisionModels = []) {
  const available = new Set(ids);
  const verified = new Set(verifiedVisionModels);
  const models = CATALOG.filter((model) => available.has(model.id)).map((model) => Object.freeze({
    id: model.id, name: model.name,
    ...(model.visionSupported || verified.has(model.id) ? { input: ['text', 'image'] } : {}),
  }));
  return Object.freeze({ displayName: 'OpenCode RT', apiKeyEnv: OPENCODE_RT_CREDENTIAL, api: 'openai-completions', baseURL: OPENCODE_RT_ENDPOINT, defaultInput: ['text'], models });
}

export class OpenCodeRtService {
  constructor({ settings, credentials, fetchImpl = globalThis.fetch } = {}) { this.settings = settings; this.credentials = credentials; this.fetch = fetchImpl; this.last = undefined; }
  configuredModels() {
    const profile = this.settings.get('llm-pi-ai')?.providers?.[OPENCODE_RT_PROVIDER];
    return Array.isArray(profile?.models) ? profile.models.map((model) => model.id).filter((id) => typeof id === 'string') : [];
  }
  status() {
    const configured = this.configuredModels();
    const verified = this.settings.get('mathmodel-opencode-rt')?.verifiedVisionModels ?? [];
    return Object.freeze({ schema: 'dsh.mathmodel.opencode-rt/v1', endpoint: OPENCODE_RT_MODELS_ENDPOINT, configuredModels: configured, visionCandidates: CATALOG.filter((model) => model.visionSupported).map((model) => model.id), verifiedVisionModels: verified.filter((id) => configured.includes(id)), ...(this.last ? { last: this.last } : {}) });
  }
  async refresh({ signal } = {}) {
    let response;
    try { response = await this.fetch(OPENCODE_RT_MODELS_ENDPOINT, { headers: { accept: 'application/json' }, signal }); }
    catch { if (signal?.aborted) throw fail('cancelled', 'OpenCode 模型刷新已取消'); throw fail('models_unavailable', '无法连接 OpenCode 模型接口'); }
    if (!response?.ok) throw fail('models_http_error', `OpenCode 模型接口请求失败（HTTP ${response?.status ?? '未知'}）`);
    const ids = parseOpenCodeModels(await response.json());
    const verified = this.settings.get('mathmodel-opencode-rt')?.verifiedVisionModels ?? [];
    const profile = buildOpenCodeRtProfile(ids, verified);
    if (profile.models.length === 0) throw fail('no_supported_models', '官方模型清单中没有可安全接入 opencode-rt 的模型');
    await this.settings.mutate('llm-pi-ai', [{ op: 'set', path: ['providers', OPENCODE_RT_PROVIDER], value: profile }]);
    const selected = new Set(profile.models.map((model) => model.id));
    this.last = Object.freeze({ refreshedAt: new Date().toISOString(), remoteCount: ids.length, applied: profile.models.map((model) => model.id), pending: ids.filter((id) => !selected.has(id)) });
    return this.status();
  }
  async configure(apiKey, { signal } = {}) {
    const supplied = typeof apiKey === 'string' ? apiKey.trim() : '';
    const existing = supplied ? undefined : await this.credentials.resolve(OPENCODE_RT_CREDENTIAL);
    if (!supplied && !existing?.value) throw fail('credential_missing', '请输入 OpenCode API Key，或先配置 opencode-go');
    try {
      if (supplied) await this.credentials.set(OPENCODE_RT_CREDENTIAL, supplied);
      return await this.refresh({ signal });
    } catch (error) {
      throw safeError(error, [supplied, existing?.value]);
    }
  }
  async verifyVision(model, { signal } = {}) {
    const entry = CATALOG_BY_ID.get(model);
    if (!entry?.visionSupported) throw fail('vision_not_declared', '该模型尚未声明为可验收的识图模型');
    if (!this.configuredModels().includes(model)) throw fail('model_not_configured', '请先刷新模型列表，再验证该模型');
    const credential = await this.credentials.resolve(OPENCODE_RT_CREDENTIAL);
    if (!credential?.value) throw fail('credential_missing', '尚未配置 OpenCode API Key，无法进行识图验收');
    let response;
    try {
      response = await this.fetch(`${OPENCODE_RT_ENDPOINT}/chat/completions`, { method: 'POST', signal, headers: { authorization: `Bearer ${credential.value}`, 'content-type': 'application/json' }, body: JSON.stringify({ model, max_tokens: 32, messages: [{ role: 'user', content: [{ type: 'text', text: '请仅回复 OK。' }, { type: 'image_url', image_url: { url: TINY_PNG } }] }] }) });
    } catch { if (signal?.aborted) throw fail('cancelled', '识图验收已取消'); throw fail('vision_unavailable', '无法连接 OpenCode 识图接口'); }
    if (!response?.ok) throw fail('vision_http_error', `模型未通过识图验收（HTTP ${response?.status ?? '未知'}）`);
    if (!textOf((await response.json())?.choices?.[0]?.message?.content)) throw fail('vision_invalid_response', '模型返回为空，未通过识图验收');
    const current = this.settings.get('mathmodel-opencode-rt')?.verifiedVisionModels ?? [];
    const verified = [...new Set([...current, model])];
    await this.settings.update('mathmodel-opencode-rt', { verifiedVisionModels: verified });
    await this.settings.mutate('llm-pi-ai', [{ op: 'set', path: ['providers', OPENCODE_RT_PROVIDER], value: buildOpenCodeRtProfile(this.configuredModels(), verified) }]);
    return Object.freeze({ model, verified: true });
  }
}
