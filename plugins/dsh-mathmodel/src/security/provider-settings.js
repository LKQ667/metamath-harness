export const PROVIDERS = Object.freeze(['dashscope', 'openai', 'gemini', 'custom']);
export const DEFAULT_PROVIDER_SETTINGS = Object.freeze({
  providerOrder: Object.freeze([...PROVIDERS]),
  dashscopeModel: 'wan2.7-image-pro',
  openaiModel: 'gpt-image-1',
  geminiModel: 'gemini-3.1-flash-image',
  customBaseUrl: '',
  customModel: '',
});
const KEYS = new Set(Object.keys(DEFAULT_PROVIDER_SETTINGS));

export function validateProviderSettings(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) throw new TypeError('供应商设置必须是对象');
  for (const key of Object.keys(raw)) if (!KEYS.has(key)) throw new TypeError(`未知供应商设置：${key}`);
  const value = { ...DEFAULT_PROVIDER_SETTINGS, ...raw };
  if (!Array.isArray(value.providerOrder) || value.providerOrder.length !== PROVIDERS.length || new Set(value.providerOrder).size !== PROVIDERS.length || value.providerOrder.some((item) => !PROVIDERS.includes(item))) {
    throw new TypeError('providerOrder 必须且只能包含四个供应商各一次');
  }
  for (const key of ['dashscopeModel', 'openaiModel', 'geminiModel', 'customBaseUrl', 'customModel']) {
    if (typeof value[key] !== 'string') throw new TypeError(`${key} 必须是字符串`);
  }
  for (const key of ['dashscopeModel', 'openaiModel', 'geminiModel']) {
    if (!value[key].trim()) throw new TypeError(`${key} 不能为空`);
  }
  if (value.customBaseUrl) {
    let url;
    try {
      url = new URL(value.customBaseUrl);
    } catch {
      throw new TypeError('自定义 Base URL 必须是有效 URL');
    }
    const local = ['localhost', '127.0.0.1', '::1'].includes(url.hostname);
    if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) throw new TypeError('自定义 Base URL 必须使用 HTTPS；仅本机测试允许 HTTP');
    if (url.username || url.password) throw new TypeError('自定义 Base URL 不得内嵌凭据');
    if (!value.customModel.trim()) throw new TypeError('配置自定义 Base URL 时 customModel 不能为空');
  }
  return Object.freeze({ ...value, providerOrder: Object.freeze([...value.providerOrder]) });
}

export class ProviderSettingsFacade {
  constructor(scope) {
    this.scope = scope;
  }

  describe() {
    return validateProviderSettings(this.scope.get());
  }

  async update(patch) {
    validateProviderSettings({ ...this.scope.get(), ...patch });
    await this.scope.update(patch);
    return this.describe();
  }

  async reset() {
    await this.scope.replace({});
    return this.describe();
  }
}
