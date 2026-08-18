import { createHash, randomBytes } from 'node:crypto';

export const IMAGE_CONNECTIONS_SCHEMA_TAG = 'dsh.mathmodel.image-connections/v2';
export const MAX_CONNECTIONS = 32;
export const CONNECTION_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{7,63}$/;
export const LEGACY_PROVIDERS = Object.freeze(['dashscope', 'openai', 'gemini', 'custom']);

const REF_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const ISO_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
const FINGERPRINT_PATTERN = /^[0-9a-f]{64}$/;

export function fail(code, message) {
  const error = new TypeError(message);
  error.code = code;
  return error;
}

/** 连接模板：默认/固定 Base URL、默认适配器、允许适配器集、默认模型策略与能力状态。 */
export const IMAGE_TEMPLATES = Object.freeze([
  Object.freeze({
    id: 'dashscope', name: '百炼', capability: 'official-known', baseUrlEditable: false,
    fixedBaseUrl: 'https://dashscope.aliyuncs.com/api/v1', defaultAdapter: 'dashscope-async', adapters: ['dashscope-async'],
    defaultModel: 'wan2.7-image-pro', modelHint: '百炼官方生图模型',
  }),
  Object.freeze({
    id: 'openai', name: 'OpenAI', capability: 'official-known', baseUrlEditable: false,
    fixedBaseUrl: 'https://api.openai.com/v1', defaultAdapter: 'openai-images', adapters: ['openai-images'],
    defaultModel: 'gpt-image-1', modelHint: 'OpenAI 官方生图模型',
  }),
  Object.freeze({
    id: 'gemini', name: 'Gemini', capability: 'official-known', baseUrlEditable: false,
    fixedBaseUrl: 'https://generativelanguage.googleapis.com/v1beta', defaultAdapter: 'gemini-content', adapters: ['gemini-content'],
    defaultModel: 'gemini-3.1-flash-image', modelHint: 'Gemini 官方生图模型',
  }),
  Object.freeze({
    id: 'volcengine-ark', name: '火山引擎 Ark', capability: 'pending', baseUrlEditable: true,
    defaultBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultAdapter: 'openai-images', adapters: ['openai-images'],
    defaultModel: 'doubao-seedream-5.0-lite', modelHint: '官方模型 ID 或火山推理接入点 ID；使用图片专用 Images API',
  }),
  Object.freeze({
    id: 'sub2api', name: 'Sub2API', capability: 'pending', baseUrlEditable: true,
    defaultBaseUrl: 'http://localhost:8080/v1', defaultAdapter: 'sub2api-async-images', adapters: ['sub2api-async-images', 'openai-images'],
    defaultModel: '', modelHint: '不预置“必然可用”模型，请按实际服务填写',
  }),
  Object.freeze({
    id: 'cliproxyapi', name: 'CLIProxyAPI', capability: 'pending', baseUrlEditable: true,
    defaultBaseUrl: 'http://127.0.0.1:8317/v1', defaultAdapter: 'openai-images', adapters: ['openai-images'],
    defaultModel: '', modelHint: '仅提示 gpt-image-2 候选，请按实际服务填写',
  }),
  Object.freeze({
    id: 'openai-compatible', name: '自定义 OpenAI 兼容', capability: 'pending', baseUrlEditable: true,
    defaultBaseUrl: '', defaultAdapter: 'openai-images', adapters: ['openai-images', 'openai-chat-image'],
    defaultModel: '', modelHint: '通用兼容网关；测试可确认 openai-chat-image 协议',
  }),
  Object.freeze({
    id: 'codex-subscription', name: 'ChatGPT 订阅', capability: 'pending', baseUrlEditable: false,
    fixedBaseUrl: 'https://chatgpt.com/backend-api', defaultAdapter: 'codex-images', adapters: ['codex-images'],
    defaultModel: 'gpt-image-2', modelHint: '复用 OAuth/订阅插件的 openai-codex 登录（pi-ai-oauth.json），无需 API Key；'
      + '走 ChatGPT 订阅 Codex 生图端点（gpt-image-2）。非官方支持端点，存在账号限制风险',
  }),
]);

const TEMPLATE_BY_ID = new Map(IMAGE_TEMPLATES.map((template) => [template.id, template]));

export function templateById(id) {
  const template = TEMPLATE_BY_ID.get(id);
  if (!template) throw fail('unknown_template', `未知连接模板：${id}`);
  return template;
}

export function adapterIds() {
  return Object.freeze([...new Set(IMAGE_TEMPLATES.flatMap((template) => template.adapters))]);
}

function isIpV4Literal(hostname) {
  const parts = hostname.split('.');
  if (parts.length !== 4) return false;
  return parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255);
}

function ipV4Parts(hostname) {
  return hostname.split('.').map((part) => Number(part));
}

function isIpV6Literal(hostname) {
  return hostname.includes(':');
}

function isPrivateIpLiteral(hostname) {
  const lower = hostname.toLowerCase();
  if (isIpV4Literal(lower)) {
    const [a, b] = ipV4Parts(lower);
    if (a === 10) return true; // 10/8
    if (a === 172 && b >= 16 && b <= 31) return true; // 172.16/12
    if (a === 192 && b === 168) return true; // 192.168/16
    if (a === 169 && b === 254) return true; // 169.254/16
    if (a === 0) return true; // 0.0.0.0/8
    if (a === 127) return lower !== '127.0.0.1'; // 回环，除显式放行项
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT 100.64/10
    return false;
  }
  if (isIpV6Literal(lower)) {
    if (lower === '::' || lower === '::1') return lower !== '::1';
    const first = Number.parseInt(lower.split(':')[0] || '0', 16) || 0;
    if ((first & 0xfe00) === 0xfc00) return true; // fc00::/7
    if ((first & 0xffc0) === 0xfe80) return true; // fe80::/10
    return false;
  }
  return false;
}

function hasSecretQuery(searchParams) {
  for (const key of searchParams.keys()) {
    if (/key|token|secret|password|passwd|sig|signature/i.test(key)) return true;
  }
  return false;
}

/** 校验并规范化 Base URL：去尾部 /、仅 HTTPS（本机网关允许 HTTP）、无内嵌凭据、无内网 IP、无密钥型查询参数。 */
export function validateBaseUrl(raw) {
  if (typeof raw !== 'string' || !raw.trim()) throw fail('invalid_base_url', 'Base URL 不能为空');
  let url;
  try {
    url = new URL(raw.trim());
  } catch {
    throw fail('invalid_base_url', 'Base URL 必须是有效 URL');
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') throw fail('invalid_base_url', 'Base URL 仅支持 HTTPS（本机网关允许 HTTP）');
  if (url.username || url.password) throw fail('base_url_credentials', 'Base URL 不得内嵌用户名或密码');
  const local = ['localhost', '127.0.0.1', '::1'].includes(url.hostname.toLowerCase());
  if (url.protocol !== 'https:' && !local) throw fail('insecure_base_url', 'Base URL 必须使用 HTTPS；仅 localhost/127.0.0.1/::1 开发网关允许 HTTP');
  if (isPrivateIpLiteral(url.hostname)) throw fail('private_base_url', 'Base URL 禁止使用内网 IP');
  if (hasSecretQuery(url.searchParams)) throw fail('base_url_secret_query', 'Base URL 禁止在查询参数中携带密钥');
  return url.toString().replace(/\/+$/, '');
}

/** 服务端生成连接 ID：img_<base36 时间戳>_<8 位随机>，符合 [a-z0-9_-] 且 8–64 字符。 */
export function generateConnectionId(now = Date.now()) {
  return `img_${now.toString(36)}_${randomBytes(4).toString('hex')}`;
}

export function isValidConnectionId(id) {
  return typeof id === 'string' && CONNECTION_ID_PATTERN.test(id);
}

/** 校验 upsert 草稿（客户端可编辑字段；id/credentialRef/verification 由服务端管理）。 */
export function validateConnectionDraft(draft, { partial = false } = {}) {
  if (draft === null || typeof draft !== 'object' || Array.isArray(draft)) throw fail('invalid_draft', '连接草稿必须是对象');
  const allowed = new Set(['name', 'template', 'adapter', 'model', 'baseUrl']);
  for (const key of Object.keys(draft)) if (!allowed.has(key)) throw fail('unknown_draft_field', `连接草稿包含未知字段：${key}`);

  const name = typeof draft.name === 'string' ? draft.name.trim() : '';
  if (!name) throw fail('invalid_name', '连接名称不能为空');
  if (name.length > 64) throw fail('invalid_name', '连接名称最多 64 个字符');

  const templateId = typeof draft.template === 'string' ? draft.template.trim() : '';
  const template = TEMPLATE_BY_ID.get(templateId);
  if (!template) throw fail('unknown_template', `未知连接模板：${templateId}`);

  const adapter = typeof draft.adapter === 'string' ? draft.adapter.trim() : '';
  if (!template.adapters.includes(adapter)) throw fail('adapter_not_allowed', `模板 ${templateId} 不允许适配器 ${adapter || '(空)'}`);

  const model = typeof draft.model === 'string' ? draft.model.trim() : '';
  if (!model) throw fail('empty_model', '模型不能为空');
  if (model.length > 160) throw fail('invalid_model', '模型最多 160 个字符');

  let baseUrl;
  if (template.baseUrlEditable) {
    if (typeof draft.baseUrl !== 'string' || !draft.baseUrl.trim()) throw fail('missing_base_url', '该模板必须填写 Base URL');
    baseUrl = validateBaseUrl(draft.baseUrl);
  } else {
    if (draft.baseUrl !== undefined && draft.baseUrl !== '') throw fail('fixed_base_url', '该模板使用官方固定接口，不能修改 Base URL');
    baseUrl = template.fixedBaseUrl;
  }
  return Object.freeze({ name, template: template.id, adapter, model, baseUrl });
}

function validateIso(value, field) {
  if (typeof value !== 'string' || !ISO_PATTERN.test(value) || Number.isNaN(Date.parse(value))) {
    throw fail('invalid_timestamp', `${field} 必须是 ISO-8601 时间`);
  }
}

function validateVerification(verification, templateId, model, baseUrl) {
  if (verification === undefined || verification === null) return undefined;
  if (typeof verification !== 'object' || Array.isArray(verification)) throw fail('invalid_verification', '验证记录必须是对象');
  const allowed = new Set(['status', 'protocol', 'model', 'template', 'baseUrlFingerprint', 'keyFingerprint', 'verifiedAt', 'message']);
  for (const key of Object.keys(verification)) if (!allowed.has(key)) throw fail('invalid_verification', `验证记录包含未知字段：${key}`);
  const status = verification.status;
  if (status === '') return undefined; // schemastery 物化的空记录视为无验证
  if (!['ready', 'failed'].includes(status)) throw fail('invalid_verification', '验证状态必须是 ready 或 failed');
  const protocol = typeof verification.protocol === 'string' ? verification.protocol : '';
  if (!adapterIds().includes(protocol)) throw fail('invalid_verification', '验证协议无效');
  if (typeof verification.model !== 'string' || !verification.model.trim()) throw fail('invalid_verification', '验证记录缺少模型');
  if (verification.template !== templateId) throw fail('invalid_verification', '验证记录的模板与连接不一致');
  if (typeof verification.baseUrlFingerprint !== 'string' || !FINGERPRINT_PATTERN.test(verification.baseUrlFingerprint)) throw fail('invalid_verification', 'Base URL 指纹无效');
  if (typeof verification.keyFingerprint !== 'string' || !FINGERPRINT_PATTERN.test(verification.keyFingerprint)) throw fail('invalid_verification', 'Key 指纹无效');
  validateIso(verification.verifiedAt, '验证时间');
  if (verification.message !== undefined && typeof verification.message !== 'string') throw fail('invalid_verification', '验证消息必须是字符串');
  return Object.freeze({ ...verification, protocol, model: verification.model.trim(), message: verification.message ?? '' });
}

function validateConnection(connection, index) {
  if (connection === null || typeof connection !== 'object' || Array.isArray(connection)) throw fail('invalid_connection', `第 ${index + 1} 条连接必须是对象`);
  const allowed = new Set(['id', 'name', 'template', 'adapter', 'model', 'baseUrl', 'credentialRef', 'createdAt', 'updatedAt', 'legacyProvider', 'verification']);
  for (const key of Object.keys(connection)) if (!allowed.has(key)) throw fail('invalid_connection', `连接包含未知字段：${key}`);
  const id = typeof connection.id === 'string' ? connection.id : '';
  if (!CONNECTION_ID_PATTERN.test(id)) throw fail('invalid_connection_id', '连接 ID 必须为 8–64 位小写字母/数字/下划线/连字符');
  const name = typeof connection.name === 'string' ? connection.name.trim() : '';
  if (!name || name.length > 64) throw fail('invalid_name', '连接名称必须为 1–64 个字符');
  const templateId = typeof connection.template === 'string' ? connection.template : '';
  const template = TEMPLATE_BY_ID.get(templateId);
  if (!template) throw fail('unknown_template', `连接 ${id} 的模板未知：${templateId}`);
  const adapter = typeof connection.adapter === 'string' ? connection.adapter : '';
  if (!template.adapters.includes(adapter)) throw fail('adapter_not_allowed', `连接 ${id} 的适配器不属于模板允许集`);
  const model = typeof connection.model === 'string' ? connection.model.trim() : '';
  if (!model || model.length > 160) throw fail('invalid_model', `连接 ${id} 的模型必须为 1–160 个字符`);
  let baseUrl;
  if (template.baseUrlEditable) {
    baseUrl = validateBaseUrl(typeof connection.baseUrl === 'string' ? connection.baseUrl : '');
  } else if (connection.baseUrl !== template.fixedBaseUrl) {
    throw fail('fixed_base_url', `连接 ${id} 必须使用官方固定 Base URL`);
  } else {
    baseUrl = template.fixedBaseUrl;
  }
  const credentialRef = typeof connection.credentialRef === 'string' ? connection.credentialRef : '';
  if (!REF_PATTERN.test(credentialRef)) throw fail('invalid_credential_ref', `连接 ${id} 的凭据引用无效`);
  validateIso(connection.createdAt, '创建时间');
  validateIso(connection.updatedAt, '更新时间');
  const legacyProvider = connection.legacyProvider || undefined;
  if (legacyProvider !== undefined && !LEGACY_PROVIDERS.includes(legacyProvider)) throw fail('invalid_legacy_provider', `连接 ${id} 的旧供应商标记无效`);
  const verification = validateVerification(connection.verification, templateId, model, baseUrl);
  return Object.freeze({
    id,
    name,
    template: templateId,
    adapter,
    model,
    baseUrl,
    credentialRef,
    createdAt: connection.createdAt,
    updatedAt: connection.updatedAt,
    ...(legacyProvider !== undefined ? { legacyProvider } : {}),
    ...(verification !== undefined ? { verification } : {}),
  });
}

/** 严格校验整个 v2 设置值；非法即抛错（settings validate 钩子与 facade 共用）。 */
export function validateImageConnections(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw fail('invalid_settings', '生图连接设置必须是对象');
  const allowed = new Set(['schema', 'activeConnectionId', 'connections']);
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw fail('unknown_settings_field', `生图连接设置包含未知字段：${key}`);
  if (value.schema !== IMAGE_CONNECTIONS_SCHEMA_TAG) throw fail('invalid_schema', `生图连接设置 schema 必须是 ${IMAGE_CONNECTIONS_SCHEMA_TAG}`);
  const connections = Array.isArray(value.connections) ? value.connections : [];
  if (connections.length > MAX_CONNECTIONS) throw fail('too_many_connections', `生图连接最多 ${MAX_CONNECTIONS} 条`);
  const seenIds = new Set();
  const seenRefs = new Set();
  const validated = connections.map((connection, index) => {
    const normalized = validateConnection(connection, index);
    if (seenIds.has(normalized.id)) throw fail('duplicate_connection_id', `重复的连接 ID：${normalized.id}`);
    seenIds.add(normalized.id);
    if (seenRefs.has(normalized.credentialRef)) throw fail('duplicate_credential_ref', `重复的凭据引用：${normalized.credentialRef}`);
    seenRefs.add(normalized.credentialRef);
    return normalized;
  });
  const activeConnectionId = typeof value.activeConnectionId === 'string' ? value.activeConnectionId : '';
  if (activeConnectionId !== '' && !seenIds.has(activeConnectionId)) throw fail('active_not_found', '当前连接指向不存在的连接');
  if (activeConnectionId !== '') {
    const active = validated.find((connection) => connection.id === activeConnectionId);
    if (active?.verification?.status !== 'ready') throw fail('active_not_ready', '当前连接必须已通过真实生图验证');
  }
  return Object.freeze({
    schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
    activeConnectionId,
    connections: Object.freeze(validated),
  });
}

export const EMPTY_IMAGE_CONNECTIONS = Object.freeze({
  schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
  activeConnectionId: '',
  connections: Object.freeze([]),
});

/** 能力状态：缺 Key / 就绪 / 验证失败 / 待验证。 */
export function capabilityOf(connection, credentialConfigured) {
  if (!credentialConfigured) return 'missing_key';
  if (connection.verification?.status === 'ready') return 'ready';
  if (connection.verification?.status === 'failed') return 'failed';
  return 'pending';
}

function legacyConnection({ id, name, templateId, model, credentialRef, now, baseUrl }) {
  const template = TEMPLATE_BY_ID.get(templateId);
  return Object.freeze({
    id, name, template: templateId,
    adapter: template.defaultAdapter,
    model, baseUrl: baseUrl ?? template.fixedBaseUrl, credentialRef,
    legacyProvider: templateId === 'openai-compatible' ? 'custom' : templateId,
    createdAt: now, updatedAt: now,
  });
}

/** v1 → v2 迁移（纯函数，不写存储）。isConfigured(ref) 由服务层注入真实凭据状态。 */
export function migrateFromV1(v1, { now = () => new Date().toISOString(), isConfigured = () => false } = {}) {
  const stamp = now();
  const connections = [];
  const legacy = (v1 === null || typeof v1 !== 'object') ? {} : v1;
  const model = (key, fallback) => (typeof legacy[key] === 'string' && legacy[key].trim()) ? legacy[key].trim() : fallback;

  connections.push(legacyConnection({
    id: 'img_legacy_dashscope', name: '百炼', templateId: 'dashscope',
    model: model('dashscopeModel', 'wan2.7-image-pro'), credentialRef: 'DASHSCOPE_API_KEY', now: stamp,
  }));
  connections.push(legacyConnection({
    id: 'img_legacy_openai', name: 'OpenAI', templateId: 'openai',
    model: model('openaiModel', 'gpt-image-1'), credentialRef: 'OPENAI_API_KEY', now: stamp,
  }));
  connections.push(legacyConnection({
    id: 'img_legacy_gemini', name: 'Gemini', templateId: 'gemini',
    model: model('geminiModel', 'gemini-3.1-flash-image'), credentialRef: 'GEMINI_API_KEY', now: stamp,
  }));
  if (typeof legacy.customBaseUrl === 'string' && legacy.customBaseUrl.trim() && typeof legacy.customModel === 'string' && legacy.customModel.trim()) {
    connections.push(legacyConnection({
      id: 'img_legacy_custom', name: '自定义', templateId: 'openai-compatible',
      model: legacy.customModel.trim(), credentialRef: 'CUSTOM_IMAGE_API_KEY', now: stamp,
      baseUrl: validateBaseUrl(legacy.customBaseUrl),
    }));
  }

  const configured = (connection) => isConfigured(connection.credentialRef);
  const order = Array.isArray(legacy.providerOrder)
    ? legacy.providerOrder.filter((item) => LEGACY_PROVIDERS.includes(item))
    : [...LEGACY_PROVIDERS];
  // v1 没有可追溯的真实验证记录，不能把“旧 Key 已配置”误当作“生图已就绪”。
  // 保留 order/isConfigured 读取是为了兼容迁移输入，但 v2 的当前连接必须由用户完成真实测试后显式设置。
  const active = order
    .map((provider) => connections.find((connection) => connection.legacyProvider === provider))
    .find((match) => match && configured(match) && TEMPLATE_BY_ID.get(match.template).capability === 'official-known' && match.verification?.status === 'ready');
  const value = {
    schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
    activeConnectionId: active ? active.id : '',
    connections,
  };
  return validateImageConnections(value);
}

/** scope 封装：写前完整校验；返回校验后的描述。 */
export class ImageConnectionsFacade {
  constructor(scope) {
    this.scope = scope;
  }

  describe() {
    return validateImageConnections(this.scope.get());
  }

  async update(patch) {
    const next = validateImageConnections({ ...this.scope.get(), ...patch });
    await this.scope.update(next);
    return this.describe();
  }

  async replace(section) {
    const next = validateImageConnections(section);
    await this.scope.replace(next);
    return this.describe();
  }

  static fingerprint(value) {
    return createHash('sha256').update(String(value)).digest('hex');
  }
}
