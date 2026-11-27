import type { Context } from '@deepseek-ai/cordis';
import type { RetryPolicyConfig } from '@deepseek-ai/dsh-llm';
import z from '@deepseek-ai/schemastery';
import { type Context as PiContext, type Model } from '@earendil-works/pi-ai';
import type { AssistantMessageEventStream } from '@earendil-works/pi-ai/utils/event-stream';
export declare const name = "cline-free-provider";
export declare const inject: string[];
interface ReasoningMetadata {
    /** Effort ids the OpenRouter secondary scan credits this model with. */
    supportedEfforts?: string[];
    /** Upstream says thinking cannot be turned off on this model. */
    mandatory?: boolean;
}
interface ClineModel {
    id: string;
    name?: string;
    contextWindow?: number;
    maxTokens?: number;
    /** Whether the Cline feed lists `reasoning_effort` among its `supported_parameters`. */
    supportsReasoningEffort?: boolean;
    /** Whether the feed's `architecture.input_modalities` names `image`. */
    imageInput?: boolean;
    /** Optional ladder from the OpenRouter secondary scan (absent if that scan failed). */
    reasoning?: ReasoningMetadata;
}
export interface Config {
    apiKeyEnv?: string;
    /** 额外的凭据 ref 列表；非空时启用多 Key 号池（轮询 + 失败冷却 + 请求级故障转移）。 */
    apiKeyEnvPool?: string[];
    /** 卡片待清理的凭据名称；不参与轮询，不包含凭据值。 */
    apiKeyCleanupRefs?: string[];
    /** 429/403 等可重试失败后的 Key 冷却时长（毫秒）。 */
    poolCooldownMs?: number;
    /** 401/Key 无效类失败后的冷却时长（毫秒），默认更长。 */
    poolInvalidKeyCooldownMs?: number;
    baseURL?: string;
    defaultMaxTokens?: number;
    defaultContextWindow?: number;
    /** Provider-owned model-request retry policy; omission uses normal defaults. */
    retryPolicy?: RetryPolicyConfig;
}
export declare const Config: z<Config>;
export declare function fetchFreeModels(url?: string, fetchImpl?: typeof fetch): Promise<ClineModel[]>;
export declare function fetchOpenRouterReasoning(url?: string, fetchImpl?: typeof fetch): Promise<Map<string, ReasoningMetadata>>;
/** Key 池控制器：由 apply() 提供，createApi 消费。 */
interface KeyPool {
    /** 是否启用多 Key 池。 */
    enabled(): boolean;
    /** 可重试失败（429/403/限流）的冷却毫秒。 */
    cooldownMs(): number;
    /** Key 无效（401）的冷却毫秒。 */
    invalidCooldownMs(): number;
    /** 标记一把 Key 进入冷却（按 Key 值记，不落日志）。 */
    cool(key: string, ms: number): void;
    /** 取全部可用（未冷却）的 Key 值，按轮询游标排序。预检查用：peek，不推进游标。 */
    peekUsableKeys(): Promise<string[]>;
    /** 为一个请求分配一次轮询顺序（推进游标）。实际发送专用：每请求只调用一次。 */
    usableKeys(): Promise<string[]>;
    warn(message: string): void;
}
type AttemptKind = 'stream' | 'streamSimple';
type AttemptFn = (kind: AttemptKind, model: Model<any>, context: PiContext, options: unknown, apiKey: string | undefined) => AssistantMessageEventStream;
/**
 * 请求级故障转移（M03 语义）：
 * - 可归因 Key 的 401/403/429 等失败先按既有分类冷却，无论之后是否重放；
 * - 尚未暴露内容时允许有界切换（每把本次至多尝试一次）；已暴露内容后不重放，
 *   透传真实失败；
 * - 空池/全冷却/所有 Key 失败明确终止，不退回未指定池 Key 的额外尝试。
 */
declare function failoverStream(kind: AttemptKind, pool: KeyPool, model: Model<any>, context: PiContext, options: unknown, attempt?: AttemptFn): AssistantMessageEventStream;
/** 供测试注入模拟 attempt（M02/M03 行为回归），不影响运行时调用路径。 */
export { failoverStream };
/** 运行时与回归测试使用同一个池实现；凭据由宿主解析。 */
export declare function createKeyPool(ctx: Context, current: () => Config): KeyPool;
export declare function apply(ctx: Context, config: Config): Promise<void>;
