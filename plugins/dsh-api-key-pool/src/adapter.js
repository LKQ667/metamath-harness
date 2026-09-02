import { AsyncLocalStorage } from 'node:async_hooks';
import { LlmError, resolveRetryPolicy } from '@deepseek-ai/dsh-llm';
import { PiAiAdapter } from '@deepseek-ai/dsh-llm-pi-ai';
import { createProvider } from '@earendil-works/pi-ai';
import { openAICompletionsApi } from '@earendil-works/pi-ai/api/openai-completions.lazy';
import { openAIResponsesApi } from '@earendil-works/pi-ai/api/openai-responses.lazy';
import { anthropicMessagesApi } from '@earendil-works/pi-ai/api/anthropic-messages.lazy';
import { routeOf } from './schema.js';
import { POOL_EXHAUSTED_CODE } from './pools.js';

/**
 * PoolPiAiAdapter：继承官方 PiAiAdapter，仅覆写 streamWithSnapshot 做
 * 「逐流 Key 快照（ALS）+ 结果观测」。全部流协议/watchdog/重放逻辑复用父类。
 */

const PROTOCOLS = {
  'openai-completions': openAICompletionsApi,
  'openai-responses': openAIResponsesApi,
  'anthropic-messages': anthropicMessagesApi,
};

const NO_COST = Object.freeze({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });

const DEFAULT_STREAM_IDLE_TIMEOUT_MS = 300_000;
const DEFAULT_MAX_REQUEST_IMAGE_BYTES = 20 * 1024 * 1024;
const DEFAULT_REQUEST_IMAGE_PIXEL_BUDGET = 2048 * 2048;
const DEFAULT_REQUEST_IMAGE_MAX_BYTES = 1024 * 1024;

/** 与官方 harnessApiKeyAuth 等价：credential.key → 请求 auth.apiKey。 */
function poolApiKeyAuth(name) {
  return {
    name,
    resolve: ({ credential }) => Promise.resolve({
      auth: credential?.key === undefined ? {} : { apiKey: credential.key },
      source: name,
    }),
  };
}

/** 手声明 pool route 的 pi-ai Provider（完整复刻 dsh-llm-pi-ai buildProvider 手声明路径）。 */
export function buildPoolProvider(route, pool) {
  const factory = PROTOCOLS[pool.api];
  if (factory === undefined) {
    throw new Error(`dsh-api-key-pool: 池 "${route}" 的 api "${pool.api}" 无可用线协议实现`);
  }
  return createProvider({
    id: route,
    name: pool.displayName,
    baseUrl: pool.baseURL,
    auth: { apiKey: poolApiKeyAuth(pool.displayName) },
    models: pool.models.map((model) => ({
      id: model.id,
      name: model.name,
      api: pool.api,
      provider: route,
      baseUrl: pool.baseURL,
      // 号池默认只声明文本；勾选「识图」后写 [text, image]，父类才会允许图片附件上行
      input: model.input ?? ['text'],
      cost: NO_COST,
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens,
      reasoning: false,
    })),
    api: factory(),
  });
}

/**
 * 把规范化号池配置解析为 PiAiAdapter 的 profiles 快照（Map<route, resolvedProfile>）。
 * 字段对照 PiAiAdapter 读取点清单逐项补齐；retryPolicy 只声明官方 dsh-llm-retry 的次数。
 */
export function resolvePoolProfiles(config) {
  const resolved = new Map();
  for (const [poolId, pool] of Object.entries(config?.pools ?? {})) {
    if (!pool.enabled) continue;
    const route = routeOf(poolId);
    const configuredMaxTokens = new Map(pool.models.map((model) => [model.id, model.maxTokens]));
    resolved.set(route, {
      provider: route,
      displayName: pool.displayName,
      streamIdleTimeoutMs: DEFAULT_STREAM_IDLE_TIMEOUT_MS,
      maxRequestImageBytes: DEFAULT_MAX_REQUEST_IMAGE_BYTES,
      requestImagePixelBudget: DEFAULT_REQUEST_IMAGE_PIXEL_BUDGET,
      requestImageMaxBytes: DEFAULT_REQUEST_IMAGE_MAX_BYTES,
      retryPolicy: resolveRetryPolicy(
        { mode: 'normal', maxRetries: pool.maxRetries },
        `dsh-api-key-pool: 池 "${route}" retryPolicy`,
      ),
      configuredMaxTokens,
      piProvider: buildPoolProvider(route, pool),
    });
  }
  return resolved;
}

/** 逐流 Key 会话（AsyncLocalStorage）：并发流各自持有不可变 Key 快照，天然防串 Key。 */
export const keySession = new AsyncLocalStorage();

/** 供父类 config.resolveApiKey 读取的闭包：只承认 ALS 中当前流的 Key。 */
export function makeResolveApiKey() {
  return async (provider) => {
    const session = keySession.getStore();
    if (session !== undefined) return session.value;
    throw new LlmError(
      `dsh-api-key-pool: 流上下文缺失 Key 快照（route "${provider}"）；请通过 KeyPoolRuntime.beginStream 发起请求`,
      'POOL_KEY_CONTEXT_MISSING',
    );
  };
}

/** 观测：结束 chunk 或 thrown LlmError → 健康处置。 */
function failureCodeOf(reason) {
  return reason?.failure?.code;
}

function retryAfterOf(failureSource) {
  const ms = failureSource?.providerRetryAfterMs ?? failureSource?.failure?.providerRetryAfterMs;
  return Number.isFinite(ms) && ms > 0 ? { retryAfterMs: ms } : {};
}

export class PoolPiAiAdapter extends PiAiAdapter {
  /**
   * @param {object} options
   * @param {KeyPoolRuntime} options.pools 号池运行时
   * @param {() => Map<string, object>} options.profiles 当前 profiles 快照函数
   * @param {() => object|undefined} [options.resolveAttachments] Harness 持久附件服务解析器
   */
  constructor({ pools, profiles, resolveAttachments }) {
    super({
      profiles,
      resolveApiKey: makeResolveApiKey(),
      auth: {
        credentials: {
          async read() { return undefined; },
          async list() { return []; },
          async modify() { throw new Error('dsh-api-key-pool: 池 route 不支持存储凭据'); },
          async delete() { return undefined; },
        },
        authContext: {
          async env() { return undefined; },
          async fileExists() { return false; },
        },
      },
      // 与官方 dsh-llm-pi-ai 接线一致；保持为惰性 resolver，纯文本请求不会读取附件服务
      resolveAttachments,
    });
    this.pools = pools;
  }

  /** 覆写：选 Key → ALS 快照内迭代父类流 → 观测结果 → 健康处置。 */
  async *streamWithSnapshot(options, snapshot) {
    let session;
    try {
      session = await this.pools.beginStream(options.provider);
    } catch (error) {
      if (error?.code === POOL_EXHAUSTED_CODE) {
        throw new LlmError(error.message, POOL_EXHAUSTED_CODE);
      }
      throw error;
    }
    const inner = super.streamWithSnapshot(options, snapshot);
    let settled = false;
    try {
      while (true) {
        const chunk = await keySession.run(session, () => inner.next());
        if (chunk.done) {
          settled = true;
          break;
        }
        if (chunk.value?.type === 'finish') {
          const failureCode = failureCodeOf(chunk.value.reason);
          if (failureCode !== undefined) {
            this.pools.recordFailure(options.provider, session.keyId, failureCode, retryAfterOf(chunk.value.reason));
            settled = true;
          } else {
            this.pools.recordSuccess(options.provider, session.keyId);
            settled = true;
          }
        }
        yield chunk.value;
      }
    } catch (error) {
      const code = error?.code ?? error?.failure?.code;
      if (typeof code === 'string' && code.length > 0 && code !== POOL_EXHAUSTED_CODE) {
        this.pools.recordFailure(options.provider, session.keyId, code, retryAfterOf(error));
      }
      throw error;
    } finally {
      if (!settled) {
        try { await keySession.run(session, () => inner.return(undefined)); } catch { /* 父类流已终止 */ }
      }
    }
  }
}
