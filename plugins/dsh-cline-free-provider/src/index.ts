import type { Context } from '@deepseek-ai/cordis'
import { assertUsableApiKey, errorChain, LlmError, resolveRetryPolicy, RetryPolicySchema } from '@deepseek-ai/dsh-llm'
import type { RetryPolicyConfig } from '@deepseek-ai/dsh-llm'
import { PiAiAdapter, type ResolvedPiAiProviderProfile } from '@deepseek-ai/dsh-llm-pi-ai'
import { credentialRef } from '@deepseek-ai/dsh-credentials'
import { launchEnvironmentOf } from '@deepseek-ai/dsh-launch-environment'
import { deepEqualJson } from '@deepseek-ai/dsh-util-values'
import type {} from '@deepseek-ai/dsh-settings'
import z from '@deepseek-ai/schemastery'
import { createProvider, type AssistantMessageEvent, type AuthContext, type Context as PiContext, type CredentialStore, type Model, type ProviderStreams, type ThinkingLevelMap } from '@earendil-works/pi-ai'
import { createAssistantMessageEventStream } from '@earendil-works/pi-ai/utils/event-stream'
import type { AssistantMessageEventStream } from '@earendil-works/pi-ai/utils/event-stream'
import { openAICompletionsApi } from '@earendil-works/pi-ai/api/openai-completions.lazy'

export const name = 'cline-free-provider'
export const inject = ['llm']

const NS = 'cline-free-provider'
const PROVIDER = 'cline'
const DISPLAY_NAME = 'Cline'

/** Envelope types that must stay AUTH-classified instead of being rewritten. */
const AUTH_ERROR_TYPES = new Set(['AuthError', 'authentication_error', 'invalid_api_key', 'unauthorized'])

const EXTRA_FREE_MODELS: Readonly<Record<string, string>> = {
  'deepseek/deepseek-v4-flash': 'DeepSeek V4 Flash (free)',
  'z-ai/glm-5.3-flash': 'GLM 5.3 Flash (free)',
  'meta/muse-spark-1.3': 'Muse Spark 1.3 (free)',
}

interface ReasoningMetadata {
  /** Effort ids the OpenRouter secondary scan credits this model with. */
  supportedEfforts?: string[]
  /** Upstream says thinking cannot be turned off on this model. */
  mandatory?: boolean
}

interface ClineModel {
  id: string
  name?: string
  contextWindow?: number
  maxTokens?: number
  /** Whether the Cline feed lists `reasoning_effort` among its `supported_parameters`. */
  supportsReasoningEffort?: boolean
  /** Whether the feed's `architecture.input_modalities` names `image`. */
  imageInput?: boolean
  /** Optional ladder from the OpenRouter secondary scan (absent if that scan failed). */
  reasoning?: ReasoningMetadata
}

export interface Config {
  apiKeyEnv?: string
  /** 额外的凭据 ref 列表；非空时启用多 Key 号池（轮询 + 失败冷却 + 请求级故障转移）。 */
  apiKeyEnvPool?: string[]
  /** 卡片待清理的凭据名称；不参与轮询，不包含凭据值。 */
  apiKeyCleanupRefs?: string[]
  /** 429/403 等可重试失败后的 Key 冷却时长（毫秒）。 */
  poolCooldownMs?: number
  /** 401/Key 无效类失败后的冷却时长（毫秒），默认更长。 */
  poolInvalidKeyCooldownMs?: number
  baseURL?: string
  defaultMaxTokens?: number
  defaultContextWindow?: number
  /** Provider-owned model-request retry policy; omission uses normal defaults. */
  retryPolicy?: RetryPolicyConfig
}

export const Config: z<Config> = z.object({
  apiKeyEnv: z.string().role('credential-ref').default('CLINE_API_KEY'),
  apiKeyEnvPool: z.array(z.string()).default([]),
  apiKeyCleanupRefs: z.array(z.string()).default([]),
  poolCooldownMs: z.number().step(1).min(0).default(60_000),
  poolInvalidKeyCooldownMs: z.number().step(1).min(0).default(1_800_000),
  baseURL: z.string().default('https://api.cline.bot/api/v1'),
  defaultMaxTokens: z.number().step(1).min(1).default(32_768),
  defaultContextWindow: z.number().step(1).min(1).default(262_144),
  retryPolicy: RetryPolicySchema,
})

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function positiveNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}

async function fetchJson(url: string, timeoutMs: number, label: string, fetchImpl: typeof fetch = fetch): Promise<unknown> {
  const response = await fetchImpl(url, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(timeoutMs) })
  if (!response.ok) throw new Error(`${label} endpoint answered HTTP ${response.status}`)
  return await response.json()
}

export async function fetchFreeModels(
  url: string = 'https://api.cline.bot/api/v1/ai/cline/models',
  fetchImpl: typeof fetch = fetch,
): Promise<ClineModel[]> {
  const payload = await fetchJson(url, 30_000, 'Cline models', fetchImpl)
  if (!isRecord(payload) || !Array.isArray(payload.data)) {
    throw new Error('Cline models endpoint returned an unexpected shape')
  }
  const models: ClineModel[] = []
  for (const raw of payload.data) {
    if (!isRecord(raw) || typeof raw.id !== 'string') continue
    const extraName = EXTRA_FREE_MODELS[raw.id]
    if (!raw.id.endsWith(':free') && extraName === undefined) continue
    const name = extraName ?? (typeof raw.name === 'string' && raw.name.length > 0 ? raw.name : undefined)
    const contextWindow = positiveNumber(raw.context_length)
    const maxTokens = positiveNumber(isRecord(raw.top_provider) ? raw.top_provider.max_completion_tokens : undefined)
    const supportedParameters = Array.isArray(raw.supported_parameters)
      ? (raw.supported_parameters as unknown[]).filter((x): x is string => typeof x === 'string')
      : undefined
    const architecture = isRecord(raw.architecture) ? raw.architecture : undefined
    const imageInput = architecture !== undefined && Array.isArray(architecture.input_modalities)
      && (architecture.input_modalities as unknown[]).includes('image')
    models.push({
      id: raw.id,
      ...(name === undefined ? {} : { name }),
      ...(contextWindow === undefined ? {} : { contextWindow }),
      ...(maxTokens === undefined ? {} : { maxTokens }),
      ...(supportedParameters?.includes('reasoning_effort') ? { supportsReasoningEffort: true } : {}),
      ...(imageInput ? { imageInput: true } : {}),
    })
  }
  models.sort((a, b) => a.id.localeCompare(b.id))
  return models
}

export async function fetchOpenRouterReasoning(
  url: string = 'https://openrouter.ai/api/v1/models',
  fetchImpl: typeof fetch = fetch,
): Promise<Map<string, ReasoningMetadata>> {
  const payload = await fetchJson(url, 300_000, 'OpenRouter models', fetchImpl)
  if (!isRecord(payload) || !Array.isArray(payload.data)) {
    throw new Error('OpenRouter models endpoint returned an unexpected shape')
  }
  const byId = new Map<string, ReasoningMetadata>()
  for (const raw of payload.data) {
    if (!isRecord(raw) || typeof raw.id !== 'string') continue
    const r = isRecord(raw.reasoning) ? raw.reasoning : undefined
    if (r === undefined) continue
    const efforts = Array.isArray(r.supported_efforts)
      ? (r.supported_efforts as unknown[]).filter((x): x is string => typeof x === 'string')
      : undefined
    if (efforts === undefined || efforts.length === 0) continue
    byId.set(raw.id, {
      supportedEfforts: efforts,
      ...typeof r.mandatory === 'boolean' ? { mandatory: r.mandatory } : {},
    })
  }
  return byId
}

// The Cline feed's `supported_parameters` asserts controllability, OpenRouter's
// scan supplies the ladder. Either one missing means no effort control at all —
// never a fabricated ladder.
function reasoningLevelsFor(model: ClineModel): string[] {
  if (!model.supportsReasoningEffort) return []
  const efforts = model.reasoning?.supportedEfforts
  if (efforts === undefined || efforts.length === 0) return []
  return efforts
}

/** pi-ai's standard ladder keys (off = explicit close; the rest are depths). */
const PI_LEVEL_KEYS = ['minimal', 'low', 'medium', 'high', 'xhigh', 'max'] as const

// `Default` (the harness's "no selection" path) is the *absent key* — leaving
// `reasoning_effort` off the wire and letting the upstream choose. Each ladder
// level the endpoint accepts lands at its own key with its own wire value; the
// `off` key carries the upstream's literal close value when the feed names one
// (e.g. `none`), so the selector's "Off" entry is a real switch rather than a
// no-op. Mandatory models omit the `off` key entirely — the harness then has
// no way to disable thinking.
function reasoningMapFor(levels: readonly string[], mandatory: boolean | undefined): ThinkingLevelMap {
  const map: ThinkingLevelMap = {}
  for (const key of PI_LEVEL_KEYS) {
    map[key] = levels.includes(key) ? key : null
  }
  map.off = mandatory ? null : 'none'
  return map
}

function buildModels(scanned: readonly ClineModel[], baseURL: string, config: Config): Model<'openai-completions'>[] {
  return scanned.map(model => {
    const levels = reasoningLevelsFor(model)
    const mandatory = model.reasoning?.mandatory
    const controllable = levels.length > 0
    return {
      id: model.id,
      name: model.name ?? model.id,
      api: 'openai-completions',
      provider: PROVIDER,
      baseUrl: baseURL,
      headers: {
        'User-Agent': 'Cline/3.0.47',
        'HTTP-Referer': 'https://cline.bot',
        'X-Title': 'Cline',
        'X-IS-MULTIROOT': 'false',
        'X-CLIENT-TYPE': 'cline-sdk',
        'X-CLIENT-VERSION': '3.0.47',
        'X-PLATFORM': 'terminal',
        'X-PLATFORM-VERSION': '3.0.47',
        'X-CORE-VERSION': '0.0.66',
      },
      reasoning: controllable,
      // Declared from the feed's own `architecture.input_modalities`; a model
      // the feed leaves silent stays text-only (under-claiming refuses the
      // image while it is still cheap, over-claiming leaves a durable message
      // no request can replay).
      input: model.imageInput ? ['text', 'image'] : ['text'],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      compat: { requiresReasoningContentOnAssistantMessages: false },
      contextWindow: model.contextWindow ?? config.defaultContextWindow ?? 262_144,
      maxTokens: model.maxTokens ?? config.defaultMaxTokens ?? 32_768,
      ...(controllable ? { thinkingLevelMap: reasoningMapFor(levels, mandatory) } : {}),
    }
  })
}

// Replayed thinking blocks carry no wire signature; marking them
// `reasoning_content` keeps the transport from mangling history. Never gated on
// `model.reasoning`: a model with no effort control still streams thinking.
const normalizeReasoningContext = (context: PiContext): PiContext => ({
  ...context,
  messages: context.messages.map(message => message.role !== 'assistant' ? message : {
    ...message,
    content: message.content.map(block =>
      block.type === 'thinking' && block.thinking.trim().length > 0 && block.thinkingSignature === undefined
        ? { ...block, thinkingSignature: 'reasoning_content' }
        : block),
  }),
})

// Free-tier refusals (ended promotions, region blocks) arrive as HTTP 401/403,
// which the harness classifies as AUTH and masks as "API key is invalid".
// Rewriting the envelope to `[cline <type>] <message>` gets the real reason past
// that classification; genuine auth envelopes and unparseable text pass through.
const rewriteRefusalMessage = (errorMessage: string): string => {
  const start = errorMessage.indexOf('{')
  const end = errorMessage.lastIndexOf('}')
  if (start < 0 || end <= start) return errorMessage
  let parsed: unknown
  try { parsed = JSON.parse(errorMessage.slice(start, end + 1)) } catch { return errorMessage }
  if (!isRecord(parsed)) return errorMessage
  // Accept both the raw envelope (`{"type":"error","error":{…}}`) and the
  // SDK-unwrapped inner object (`{"type":"ModelError","message":"…"}`).
  const detail = parsed.type === 'error' && isRecord(parsed.error) ? parsed.error : parsed
  const message = [detail.message, isRecord(detail.error) ? detail.error.message : undefined, detail.detail]
    .find((value): value is string => typeof value === 'string')
  if (message === undefined) return errorMessage
  const type = typeof detail.type === 'string' ? detail.type : 'Error'
  const code = typeof detail.code === 'string' ? detail.code : ''
  if (AUTH_ERROR_TYPES.has(type) || AUTH_ERROR_TYPES.has(code)) return errorMessage
  // Dropping the status prefix is what defeats the AUTH classifier.
  return `[cline ${type}] ${message}`
}

// Required by the adapter, unused by this route: the credential comes from
// `resolveApiKey`, so pi-ai never stores one nor asks an ambient question.
const PI_AUTH: { credentials: CredentialStore, authContext: AuthContext } = {
  credentials: {
    read: async () => undefined,
    list: async () => [],
    modify: async (_providerId, mutate) => mutate(undefined),
    delete: async () => {},
  },
  authContext: { env: async () => undefined, fileExists: async () => false },
}

const sanitizeStream = <S extends { push(event: unknown): void }>(stream: S): S => {
  const originalPush = stream.push.bind(stream)
  stream.push = (event: unknown) => {
    if (isRecord(event) && event.type === 'error' && isRecord(event.error) && typeof event.error.errorMessage === 'string') {
      event.error.errorMessage = rewriteRefusalMessage(event.error.errorMessage)
    }
    originalPush(event)
  }
  return stream
}

const CLINE_VALID_EFFORTS = new Set(['max', 'xhigh', 'high', 'medium', 'low', 'minimal', 'none'])

function sanitizePayload(params: Record<string, unknown>, explicitReasoning: unknown): void {
  if (typeof params.reasoning_effort === 'string') {
    if (explicitReasoning === undefined) {
      delete params.reasoning_effort
    } else if (params.reasoning_effort === 'off') {
      params.reasoning_effort = 'none'
    } else if (!CLINE_VALID_EFFORTS.has(params.reasoning_effort)) {
      delete params.reasoning_effort
    }
  }
}

function withPayloadSanitization<T extends { onPayload?: (payload: unknown, model: Model<any>) => unknown }>(
  options: T | undefined,
  explicitReasoning: unknown,
): T {
  const customOnPayload = options?.onPayload
  return {
    ...options,
    onPayload: async (params: unknown, model: Model<any>) => {
      let current = params
      if (customOnPayload) {
        current = (await customOnPayload(params, model)) ?? params
      }
      if (isRecord(current)) {
        sanitizePayload(current, explicitReasoning)
      }
      return current
    },
  } as T
}

/** Key 池控制器：由 apply() 提供，createApi 消费。 */
interface KeyPool {
  /** 是否启用多 Key 池。 */
  enabled(): boolean
  /** 可重试失败（429/403/限流）的冷却毫秒。 */
  cooldownMs(): number
  /** Key 无效（401）的冷却毫秒。 */
  invalidCooldownMs(): number
  /** 标记一把 Key 进入冷却（按 Key 值记，不落日志）。 */
  cool(key: string, ms: number): void
  /** 取全部可用（未冷却）的 Key 值，按轮询游标排序。预检查用：peek，不推进游标。 */
  peekUsableKeys(): Promise<string[]>
  /** 为一个请求分配一次轮询顺序（推进游标）。实际发送专用：每请求只调用一次。 */
  usableKeys(): Promise<string[]>
  warn(message: string): void
}

const baseApi = openAICompletionsApi()

/**上游拒绝里可判定为"换把 Key 可能有用"的形态：HTTP 401/403/429、配额与限流文案。 */
function isRetryableKeyError(message: string): boolean {
  return /\b(401|403|429)\b/.test(message)
    || /unauthorized|invalid[ _-]?api[ _-]?key|quota|rate[ _-]?limit|insufficient|too many requests/i.test(message)
}

function errorMessageOf(event: unknown): string {
  if (isRecord(event) && isRecord(event.error) && typeof event.error.errorMessage === 'string') {
    return event.error.errorMessage
  }
  return String(event)
}

function isKeyInvalidMessage(message: string): boolean {
  return /\b401\b/.test(message) || /unauthorized|invalid[ _-]?api[ _-]?key/i.test(message)
}

type AttemptKind = 'stream' | 'streamSimple'

type AttemptFn = (kind: AttemptKind, model: Model<any>, context: PiContext, options: unknown, apiKey: string | undefined) => AssistantMessageEventStream

function makeAttempt(kind: AttemptKind, model: Model<any>, context: PiContext, options: unknown, apiKey: string | undefined): AssistantMessageEventStream {
  const explicitReasoning = kind === 'stream'
    ? (isRecord(options) ? options.reasoningEffort : undefined)
    : (options as { reasoning?: string } | undefined)?.reasoning
  const withKey = { ...options as Record<string, unknown>, ...(apiKey === undefined ? {} : { apiKey }) }
  const inner = kind === 'stream'
    ? baseApi.stream(model, normalizeReasoningContext(context), withPayloadSanitization(withKey as never, explicitReasoning))
    : baseApi.streamSimple(model, normalizeReasoningContext(context), withPayloadSanitization(withKey as never, explicitReasoning))
  return sanitizeStream(inner)
}

/**
 * 事件里"已经向用户或工具暴露了内容"的判定（M03）：delta 与工具调用事件承载
 * 真实内容；`start`/`*_start` 等零内容生命周期事件不算，允许在其后失败时重放。
 */
const CONTENT_EVENT_TYPES: ReadonlySet<string> = new Set([
  'text_delta',
  'thinking_delta',
  'toolcall_start',
  'toolcall_delta',
  'toolcall_end',
])

/**
 * 请求级故障转移（M03 语义）：
 * - 可归因 Key 的 401/403/429 等失败先按既有分类冷却，无论之后是否重放；
 * - 尚未暴露内容时允许有界切换（每把本次至多尝试一次）；已暴露内容后不重放，
 *   透传真实失败；
 * - 空池/全冷却/所有 Key 失败明确终止，不退回未指定池 Key 的额外尝试。
 */
function failoverStream(kind: AttemptKind, pool: KeyPool, model: Model<any>, context: PiContext, options: unknown, attempt: AttemptFn = makeAttempt): AssistantMessageEventStream {
  const outer = createAssistantMessageEventStream()
  const signal = (options as { signal?: AbortSignal } | undefined)?.signal
  const cancel = () => {
    outer.push({ type: 'error', reason: 'aborted', error: {
      role: 'assistant', api: 'openai-completions', provider: PROVIDER,
      model: model.id ?? 'unknown', stopReason: 'aborted',
      errorMessage: 'Request aborted', content: [],
    } as never })
    outer.end()
  }
  if (signal?.aborted) { cancel(); return outer }
  signal?.addEventListener('abort', cancel, { once: true })
  void (async () => {
    try {
      if (!pool.enabled()) {
        for await (const event of attempt(kind, model, context, options, undefined)) {
          if (signal?.aborted) return
          outer.push(event)
          if (event.type === 'error' || event.type === 'done') return
        }
        outer.end()
        return
      }
      const keys = await pool.usableKeys()
      if (signal?.aborted) return
      if (keys.length === 0) {
        outer.push({
          type: 'error',
          reason: 'error',
          error: {
            role: 'assistant',
            api: 'openai-completions',
            provider: PROVIDER,
            model: 'unknown',
            stopReason: 'error',
            errorMessage: 'cline-free-provider: every pool key is cooling down or missing;'
              + ' add keys on the Cline Free API Key card or wait out the cooldown',
            content: [],
          } as never,
        })
        outer.end()
        return
      }
      let contentSeen = false
      let lastError: AssistantMessageEvent | undefined = undefined
      for (let attemptIndex = 0; attemptIndex < keys.length; attemptIndex++) {
        if (signal?.aborted) return
        const key = keys[attemptIndex]!
        let switched = false
        for await (const event of attempt(kind, model, context, options, key)) {
          if (signal?.aborted) return
          if (event.type === 'error') {
            const message = errorMessageOf(event)
            if (isRetryableKeyError(message)) {
              // 冷却先行：只要失败可归因到这把 Key 且可重试，就先记录冷却；
              // 是否有下一把、是否已输出内容只决定是否重放，不决定是否冷却。
              const ms = isKeyInvalidMessage(message) ? pool.invalidCooldownMs() : pool.cooldownMs()
              pool.cool(key, ms)
              if (!contentSeen && attemptIndex < keys.length - 1) {
                pool.warn(`key #${attemptIndex + 1} failed, failing over to the next pool key`)
                switched = true
                break
              }
            }
            lastError = event
            break
          }
          if (CONTENT_EVENT_TYPES.has(event.type)
            && (!(event.type === 'text_delta' || event.type === 'thinking_delta') || event.delta.length > 0)) contentSeen = true
          outer.push(event)
          if (event.type === 'done') return
        }
        if (!switched) {
          // 本轮以真实失败终止（不可重试错误，或已输出内容后失败）：透传。
          if (lastError !== undefined) outer.push(lastError)
          outer.end()
          return
        }
      }
      // 所有池内 Key 都失败且已切换到尽头：明确终止，不退回未指定池 Key 的额外尝试。
      outer.push(lastError ?? {
        type: 'error',
        reason: 'error',
        error: {
          role: 'assistant',
          api: 'openai-completions',
          provider: PROVIDER,
          model: 'unknown',
          stopReason: 'error',
          errorMessage: 'cline-free-provider: all pool keys failed',
          content: [],
        } as never,
      })
      outer.end()
    } catch (error) {
      if (signal?.aborted) return
      outer.push({
        type: 'error',
        reason: 'error',
        error: {
          role: 'assistant',
          api: 'openai-completions',
          provider: PROVIDER,
          model: 'unknown',
          stopReason: 'error',
          errorMessage: `cline-free-provider: key pool failure: ${errorChain(error)}`,
          content: [],
        } as never,
      })
      outer.end()
     } finally {
      signal?.removeEventListener('abort', cancel)
    }
  })()
  return outer
}

function createApi(pool: KeyPool): ProviderStreams {
  return {
    stream: (model, context, options) => failoverStream('stream', pool, model, context, options),
    streamSimple: (model, context, options) => failoverStream('streamSimple', pool, model, context, options),
  }
}

/** 供测试注入模拟 attempt（M02/M03 行为回归），不影响运行时调用路径。 */
export { failoverStream }

/** 运行时与回归测试使用同一个池实现；凭据由宿主解析。 */
export function createKeyPool(ctx: Context, current: () => Config): KeyPool {
  // ---- Key 池（多 Key 轮询 + 冷却）----
  const KEY_CACHE_TTL_MS = 60_000
  const keyCache: { at: number, entries: { ref: string, value: string }[] } = { at: 0, entries: [] }
  const cooldownUntil = new Map<string, number>()
  let cursor = 0

  const isPoolMode = (opts: Config): boolean => (opts.apiKeyEnvPool ?? []).length > 0

  async function loadKeys(opts: Config): Promise<{ ref: string, value: string }[]> {
    const now = Date.now()
    if (keyCache.at !== 0 && now - keyCache.at < KEY_CACHE_TTL_MS) return keyCache.entries
    const credentials = ctx.get('credentials')
    const entries: { ref: string, value: string }[] = []
    for (const rawRef of new Set(poolRefs(opts))) {
      const ref = String(rawRef)
      let value: string | undefined
      if (credentials !== undefined) {
        const hit = await credentials.resolve(credentialRef(ref))
        value = hit?.value
      } else {
        const ambient = launchEnvironmentOf(ctx).get(ref)
        value = ambient !== undefined && ambient.value.length > 0 ? ambient.value : undefined
      }
      if (value !== undefined && value.length > 0) entries.push({ ref, value })
    }
    keyCache.at = now
    keyCache.entries = entries
    return entries
  }


  const pool: KeyPool = {
    enabled: () => isPoolMode(current()),
    cooldownMs: () => current().poolCooldownMs ?? 60_000,
    invalidCooldownMs: () => current().poolInvalidKeyCooldownMs ?? 1_800_000,
    cool: (key, ms) => {
      cooldownUntil.set(key, Date.now() + ms)
      keyCache.at = 0
    },
    usableKeys: async () => {
      const now = Date.now()
      const entries = (await loadKeys(current())).filter(entry => (cooldownUntil.get(entry.value) ?? 0) <= now)
      if (entries.length === 0) return []
      const rotated: string[] = []
      for (let i = 0; i < entries.length; i++) {
        rotated.push(entries[(cursor + i) % entries.length]!.value)
      }
      cursor += 1
      return rotated
    },
    peekUsableKeys: async () => {
      const now = Date.now()
      const entries = (await loadKeys(current())).filter(entry => (cooldownUntil.get(entry.value) ?? 0) <= now)
      if (entries.length === 0) return []
      const rotated: string[] = []
      for (let i = 0; i < entries.length; i++) {
        rotated.push(entries[(cursor + i) % entries.length]!.value)
      }
      return rotated
    },
    warn: (message) => {
      ctx.logger.warn('[%s] %s', name, message)
    },
  }

  return pool
}

function poolRefs(opts: Config): string[] {
    return [opts.apiKeyEnv ?? 'CLINE_API_KEY', ...(opts.apiKeyEnvPool ?? [])]
  }


export async function apply(ctx: Context, config: Config): Promise<void> {
  let current: () => Config = () => config

  // Outside the settings-backed config, so a settings snapshot cannot clobber a
  // scan.
  let scanned: ClineModel[] = []

  const pool = createKeyPool(ctx, () => current())

  const api = createApi(pool)

  const buildProfiles = (): ReadonlyMap<string, ResolvedPiAiProviderProfile> => {
    const opts = current()
    const baseURL = opts.baseURL ?? 'https://api.cline.bot/api/v1'
    const piProvider = createProvider({
      id: PROVIDER,
      name: 'Cline',
      baseUrl: baseURL,
      auth: {
        apiKey: {
          name: 'Cline',
          resolve: ({ credential }) => Promise.resolve({
            auth: credential?.key === undefined ? {} : { apiKey: credential.key },
            source: 'Cline',
          }),
        },
      },
      models: buildModels(scanned, baseURL, opts),
      api,
    })
    const profiles = new Map<string, ResolvedPiAiProviderProfile>([
      [
        PROVIDER,
        {
          provider: PROVIDER,
          displayName: DISPLAY_NAME,
          apiKeyEnv: credentialRef(opts.apiKeyEnv ?? 'CLINE_API_KEY'),
          streamIdleTimeoutMs: 300_000,
          maxRequestImageBytes: 20_971_520,
          requestImagePixelBudget: 4_194_304,
          requestImageMaxBytes: 1_048_576,
          retryPolicy: resolveRetryPolicy(opts.retryPolicy, 'cline-free-provider: retryPolicy'),
          piProvider,
          modelErrors: new Map(),
          configuredMaxTokens: new Map(),
        },
      ],
    ])
    return profiles
  }

  // PiAiAdapter memoizes its snapshot on this Map's identity, so a fresh Map per
  // request would rebuild the whole pi-ai collection: rebuild only on change.
  let profiles = buildProfiles()

  const adapter = new PiAiAdapter({
    resolveAttachments: () => ctx.get('attachments'),
    profiles: () => profiles,
    auth: PI_AUTH,
    resolveApiKey: async (provider, profile) => {
      // 池模式：只做"有无可用 Key"的预检（peek，不推进游标，M02）；真正的选 Key
      // 与故障转移都在 api 包装层完成。
      if (pool.enabled()) {
        const keys = await pool.peekUsableKeys()
        if (keys.length === 0) {
          const refs = poolRefs(current()).map(String).join(', ')
          throw new LlmError(
            `cline-free-provider: every pool key is missing or cooling down (${refs});`
            + ' add keys on the Cline Free API Key card or wait out the cooldown',
            'MISSING_CREDENTIAL',
          )
        }
        return keys[0]
      }
      const ref = profile.apiKeyEnv
      if (ref === undefined) return undefined
      const credentials = ctx.get('credentials')
      if (credentials !== undefined) {
        const hit = await credentials.resolve(ref)
        if (hit !== undefined) return assertUsableApiKey(hit.value, 'cline-free-provider', String(ref))
      } else {
        const ambient = launchEnvironmentOf(ctx).get(String(ref))
        if (ambient !== undefined && ambient.value.length > 0) {
          return assertUsableApiKey(ambient.value, 'cline-free-provider', String(ref))
        }
      }
      throw new LlmError(
        `cline-free-provider: no API key for provider route "${provider}"; store ${String(ref)} through the credentials`
        + ` service (the web Models page writes it), or export ${String(ref)} in the launching environment`,
        'MISSING_CREDENTIAL',
      )
    },
  })

  ctx.llm.registerConfigurableProviders([
    { provider: PROVIDER, displayName: DISPLAY_NAME, settingsNs: NS, settingsPath: [] },
  ])
  ctx.llm.registerAdapter([PROVIDER], adapter)

  ctx.inject(['settings'], (settingsCtx) => {
    settingsCtx.settings.installSection(ctx, NS, Config, config, {
      setSource: (source) => {
        current = source
      },
      onChange: () => {
        profiles = buildProfiles()
      },
    })
  })

  // The catalog is fetched once at mount. Mount never awaits it: an unreachable
  // upstream must not kill the plugin.
  async function sync(): Promise<void> {
    const [entries, reasoningById] = await Promise.all([
      fetchFreeModels(),
      // Optional metadata: a failed secondary scan must not disable models.
      fetchOpenRouterReasoning().catch((error: unknown) => {
        ctx.logger.warn('[%s] OpenRouter reasoning scan failed; falling back to Cline-only metadata: %s',
          name, errorChain(error))
        return new Map<string, ReasoningMetadata>()
      }),
    ])
    const next = entries.map(entry => ({
      ...entry,
      ...(reasoningById.has(entry.id) ? { reasoning: reasoningById.get(entry.id) } : {}),
    }))
    if (next.length === 0) {
      throw new Error('no free models found; keeping the previous catalog')
    }
    if (deepEqualJson(next, scanned)) return
    scanned = next
    profiles = buildProfiles()
    ctx.logger.info('[%s] synced %d free model(s): %s', name, scanned.length, scanned.map(m => m.id).join(', '))
  }

  void sync().catch((error: unknown) => {
    ctx.logger.warn('[%s] initial catalog scan failed: %s', name, errorChain(error))
  })
}
