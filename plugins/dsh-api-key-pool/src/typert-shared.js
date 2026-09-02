import { z } from 'zod';

/**
 * Typert Remote 描述符（host 与 client 共享）。
 * 方法面（REQ-007）：list/upsertPool/deletePool/addKey/removeKey/resetCooldown/probe；
 * 输出一律脱敏（keyId/指纹/状态），删除只传 keyId，绝不回传完整 Key。
 * codec schema 必须是 zod v4 实例（官方 dsh-typert-loader 严格校验）。
 */

const PACKAGE = '@deepseek-harness/dsh-api-key-pool';

const result = (symbol) => ({ mode: 'strict', typeSymbol: symbol, schema: z.unknown() });
const parameter = (name, schema = z.string()) => ({
  name, wire: name, source: 'json',
  codec: { mode: 'strict', typeSymbol: `api-key-pool#${name}`, schema },
});
const invocation = (service, method, parameters = []) => ({
  id: `${PACKAGE}#${service}/${method}`,
  service, namespace: service, method,
  invocation: { kind: 'direct' }, parameters,
  result: result(`api-key-pool#${service}.${method}.result`),
});

/** upsertPool 入参：池配置（非秘密元数据），字段边界与 schema.js 一致。 */
const poolInputSchema = z.object({
  id: z.string().min(2).max(40),
  displayName: z.string().max(80).optional(),
  api: z.enum(['openai-completions', 'openai-responses', 'anthropic-messages']),
  baseURL: z.string().max(2048),
  models: z.array(z.object({
    id: z.string().min(1).max(200),
    name: z.string().max(200).optional(),
    contextWindow: z.number().int().min(1).max(100_000_000).optional(),
    maxTokens: z.number().int().min(1).max(10_000_000).optional(),
    // 必须显式声明：zod 对象默认剥掉未声明的键，漏了它「识图」勾选会在 wire 层消失
    input: z.array(z.enum(['text', 'image'])).min(1).max(4).optional(),
  })).min(1).max(64),
  keyIds: z.array(z.string().max(80)).max(256).optional(),
  cooldownMs: z.number().int().min(1000).max(3_600_000).optional(),
  maxCooldownMs: z.number().int().min(10_000).max(86_400_000).optional(),
  maxRetries: z.number().int().min(0).max(6).optional(),
  enabled: z.boolean().optional(),
});

export const API_KEY_POOL_INVOCATIONS = Object.freeze([
  invocation('apiKeyPool', 'list'),
  invocation('apiKeyPool', 'upsertPool', [parameter('pool', poolInputSchema)]),
  invocation('apiKeyPool', 'deletePool', [parameter('poolId')]),
  invocation('apiKeyPool', 'addKey', [parameter('value'), parameter('poolId', z.string().optional())]),
  invocation('apiKeyPool', 'removeKey', [parameter('keyId')]),
  invocation('apiKeyPool', 'resetCooldown', [parameter('route'), parameter('keyId', z.string().optional())]),
  invocation('apiKeyPool', 'probe', [parameter('poolId')]),
]);

export const API_KEY_POOL_SERVICE = 'apiKeyPool';
