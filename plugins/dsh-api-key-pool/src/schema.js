import Schema from '@deepseek-ai/schemastery';

/**
 * 号池插件设置 schema（不含任何秘密）。
 * 完整 Key 只存 credentials 记录（scope `dsh-api-key-pool`）；本 namespace 只保存
 * 传输元数据与 keyId 顺序。版本标签 dsh.api-key-pool/v1。
 */
export const API_KEY_POOL_NAMESPACE = 'api-key-pool';
export const API_KEY_POOL_SCHEMA_TAG = 'dsh.api-key-pool/v1';
export const ROUTE_PREFIX = 'pool-';
export const SELECTION_ALGORITHMS = Object.freeze(['round-robin']);
export const SUPPORTED_APIS = Object.freeze(['openai-completions', 'openai-responses', 'anthropic-messages']);
/** 模型输入模态白名单：与原生「识图（图片输入）」勾选写入的取值一致。 */
export const MODEL_MODALITIES = Object.freeze(['text', 'image']);

export const DEFAULT_COOLDOWN_MS = 30_000;
export const MIN_COOLDOWN_MS = 1_000;
export const MAX_COOLDOWN_MS = 3_600_000;
export const DEFAULT_MAX_COOLDOWN_MS = 3_600_000;
export const MIN_MAX_COOLDOWN_MS = 10_000;
export const MAX_MAX_COOLDOWN_MS = 86_400_000;
export const DEFAULT_MAX_RETRIES = 3;
export const MAX_MAX_RETRIES = 6;

const POOL_ID_PATTERN = /^[a-z][a-z0-9-]{0,38}[a-z0-9]$/;
const KEY_ID_PATTERN = /^k-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);

const modelSchema = Schema.object({
  id: Schema.string().required().description('模型 id（发送到上游的精确字符串）'),
  name: Schema.string().description('显示名（缺省为 id）'),
  contextWindow: Schema.number().role('natural').description('上下文窗口（正整数）'),
  maxTokens: Schema.number().role('natural').description('默认输出上限（正整数）'),
  input: Schema.array(Schema.string()).description('输入模态；勾选识图即 [text, image]，仅文本时不写、继承适配器默认'),
});

const poolSchema = Schema.object({
  displayName: Schema.string().description('显示名（缺省为 id）'),
  api: Schema.union(SUPPORTED_APIS.map((value) => Schema.const(value).description(value))).required()
    .description('上游线协议'),
  baseURL: Schema.string().required().description('上游 HTTPS Base URL'),
  models: Schema.array(modelSchema).required().description('模型目录（至少一条）'),
  keyIds: Schema.array(Schema.string()).default([]).description('Key 记录 id 顺序（不存 Key 本身）'),
  selection: Schema.union(SELECTION_ALGORITHMS.map((value) => Schema.const(value))).default('round-robin')
    .description('选 Key 算法（v1 仅 round-robin）'),
  cooldownMs: Schema.number().default(DEFAULT_COOLDOWN_MS).description('基础冷却毫秒数'),
  maxCooldownMs: Schema.number().default(DEFAULT_MAX_COOLDOWN_MS).description('冷却上限毫秒数'),
  maxRetries: Schema.number().default(DEFAULT_MAX_RETRIES).description('该 route 的官方重试次数上限'),
  enabled: Schema.boolean().default(true).description('是否启用（停用立即从 route 注册集合移除）'),
});

export const ApiKeyPoolSchema = Schema.object({
  schema: Schema.const(API_KEY_POOL_SCHEMA_TAG),
  allowLoopbackHttpForTests: Schema.boolean().default(false)
    .description('仅测试：允许 127.0.0.1 HTTP 上游；生产配置必须保持 false'),
  pools: Schema.dict(poolSchema).default({}).description('号池集合，键为小写连字符 id'),
}).default({ schema: API_KEY_POOL_SCHEMA_TAG, allowLoopbackHttpForTests: false, pools: {} });

/** 实际 route id 固定派生为 `pool-${id}`；禁止占用原生 route id。 */
export function routeOf(poolId) {
  return `${ROUTE_PREFIX}${poolId}`;
}

export function isPoolRoute(provider) {
  return typeof provider === 'string' && provider.startsWith(ROUTE_PREFIX);
}

/** 校验 baseURL：默认仅 HTTPS；测试开关仅放行 loopback 且不允许生产值混入。 */
export function validateBaseURL(raw, { allowLoopbackHttpForTests = false } = {}) {
  if (typeof raw !== 'string' || raw.length === 0) throw new Error('baseURL 必须是非空字符串');
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new Error(`baseURL 无法解析：${raw}`);
  }
  if (url.protocol === 'https:') return url;
  if (url.protocol === 'http:' && allowLoopbackHttpForTests && LOOPBACK_HOSTS.has(url.hostname)) return url;
  throw new Error(`baseURL 协议被拒绝（仅 HTTPS${allowLoopbackHttpForTests ? '，或测试放行的 loopback HTTP' : ''}）：${raw}`);
}

/**
 * 归一化模型输入模态：只有声明了 image 才写盘（与原生取消勾选即清空同义），
 * 且始终补齐 text；其他取值一律拒绝，避免把拼错的模态喂给 pi-ai。
 */
function normalizeModelInput(raw, poolId, modelId) {
  if (raw === undefined || raw === null) return undefined;
  if (!Array.isArray(raw)) throw new Error(`池 "${poolId}" 的模型 "${modelId}" input 必须是数组`);
  for (const modality of raw) {
    if (!MODEL_MODALITIES.includes(modality)) {
      throw new Error(`池 "${poolId}" 的模型 "${modelId}" input 含不支持的模态：${modality}`);
    }
  }
  return raw.includes('image') ? ['text', 'image'] : undefined;
}

function validateInteger(value, { min, max, fallback }) {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isInteger(n) || n < min || n > max) {
    if (fallback !== undefined) return fallback;
    throw new Error(`数值越界：${value}（允许 ${min}..${max} 的整数）`);
  }
  return n;
}

/** 深度校验整个设置分节，返回规范化副本；任何非法值以带池名的错误拒绝。 */
export function validatePoolConfig(config) {
  if (config === undefined || config === null) {
    return { schema: API_KEY_POOL_SCHEMA_TAG, allowLoopbackHttpForTests: false, pools: {} };
  }
  if (typeof config !== 'object') throw new Error('api-key-pool 设置分节必须是对象');
  const allowLoopbackHttpForTests = config.allowLoopbackHttpForTests === true;
  const rawPools = config.pools ?? {};
  if (typeof rawPools !== 'object' || Array.isArray(rawPools)) throw new Error('pools 必须是 dict');
  const pools = {};
  for (const [id, pool] of Object.entries(rawPools)) {
    if (!POOL_ID_PATTERN.test(id)) throw new Error(`池 id 非法（小写字母开头，小写字母/数字/连字符，2-40 字符）：${id}`);
    if (typeof pool !== 'object' || pool === null) throw new Error(`池 "${id}" 配置必须是对象`);
    if (pool.api === undefined) throw new Error(`池 "${id}" 缺少 api（可选：${SUPPORTED_APIS.join(', ')}）`);
    if (!SUPPORTED_APIS.includes(pool.api)) throw new Error(`池 "${id}" 的 api 不受支持：${pool.api}`);
    validateBaseURL(pool.baseURL, { allowLoopbackHttpForTests });
    if (!Array.isArray(pool.models) || pool.models.length === 0) throw new Error(`池 "${id}" 的 models 必须至少一条`);
    const seenModels = new Set();
    const models = pool.models.map((model) => {
      if (typeof model?.id !== 'string' || model.id.length === 0) throw new Error(`池 "${id}" 存在空模型 id`);
      if (seenModels.has(model.id)) throw new Error(`池 "${id}" 重复模型 "${model.id}"`);
      seenModels.add(model.id);
      const modelInput = normalizeModelInput(model.input, id, model.id);
      return {
        id: model.id,
        name: typeof model.name === 'string' && model.name.length > 0 ? model.name : model.id,
        contextWindow: validateInteger(model.contextWindow, { min: 1, max: 100_000_000, fallback: 262144 }),
        maxTokens: validateInteger(model.maxTokens, { min: 1, max: 10_000_000, fallback: 32768 }),
        ...(modelInput === undefined ? {} : { input: modelInput }),
      };
    });
    if (!Array.isArray(pool.keyIds)) throw new Error(`池 "${id}" 的 keyIds 必须是数组`);
    const seenKeys = new Set();
    for (const keyId of pool.keyIds) {
      if (!KEY_ID_PATTERN.test(String(keyId))) throw new Error(`池 "${id}" 的 keyId 非法：${String(keyId)}`);
      if (seenKeys.has(keyId)) throw new Error(`池 "${id}" 重复 keyId：${keyId}`);
      seenKeys.add(keyId);
    }
    if (pool.selection !== undefined && pool.selection !== 'round-robin') {
      throw new Error(`池 "${id}" 的 selection 仅支持 round-robin`);
    }
    pools[id] = {
      displayName: typeof pool.displayName === 'string' && pool.displayName.length > 0 ? pool.displayName : id,
      api: pool.api,
      baseURL: pool.baseURL,
      models,
      keyIds: pool.keyIds.map(String),
      selection: 'round-robin',
      cooldownMs: validateInteger(pool.cooldownMs, { min: MIN_COOLDOWN_MS, max: MAX_COOLDOWN_MS, fallback: DEFAULT_COOLDOWN_MS }),
      maxCooldownMs: validateInteger(pool.maxCooldownMs, { min: MIN_MAX_COOLDOWN_MS, max: MAX_MAX_COOLDOWN_MS, fallback: DEFAULT_MAX_COOLDOWN_MS }),
      maxRetries: validateInteger(pool.maxRetries, { min: 0, max: MAX_MAX_RETRIES, fallback: DEFAULT_MAX_RETRIES }),
      enabled: pool.enabled !== false,
    };
    if (pools[id].cooldownMs > pools[id].maxCooldownMs) throw new Error(`池 "${id}" 的 cooldownMs 超过 maxCooldownMs`);
  }
  return { schema: API_KEY_POOL_SCHEMA_TAG, allowLoopbackHttpForTests, pools };
}

/** 校验用于 settings 注册的 validate 回调；拒绝时抛错以阻止写入。 */
export function assertServiceablePoolConfig(value) {
  validatePoolConfig(value);
}
