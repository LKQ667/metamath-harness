import { assertUsableApiKey, errorChain, LlmError, resolveRetryPolicy, RetryPolicySchema } from '@deepseek-ai/dsh-llm';
import { PiAiAdapter } from '@deepseek-ai/dsh-llm-pi-ai';
import { credentialRef } from '@deepseek-ai/dsh-credentials';
import { launchEnvironmentOf } from '@deepseek-ai/dsh-launch-environment';
import { deepEqualJson } from '@deepseek-ai/dsh-util-values';
import z from '@deepseek-ai/schemastery';
import { createProvider } from '@earendil-works/pi-ai';
import { createAssistantMessageEventStream } from '@earendil-works/pi-ai/utils/event-stream';
import { openAICompletionsApi } from '@earendil-works/pi-ai/api/openai-completions.lazy';

export const name = 'cline-free-provider';
export const inject = ['llm'];
const PROVIDER = 'cline';
const DISPLAY_NAME = 'Cline';
const AUTH_ERROR_TYPES = new Set(['AuthError', 'authentication_error', 'invalid_api_key', 'unauthorized']);
const EXTRA_FREE_MODEL_IDS = new Set([
    'deepseek/deepseek-v4-flash',
    'z-ai/glm-5.3-flash',
    'meta/muse-spark-1.3',
]);
const DEFAULT_MAX_REQUEST_IMAGE_BYTES = 2_097_152;
const DEFAULT_REQUEST_IMAGE_MAX_BYTES = 1_048_576;

export const Config = z.object({
    apiKeyEnv: z.string().role('credential-ref').default('CLINE_API_KEY').volatile(),
    apiKeyEnvPool: z.array(z.string()).default([]).volatile(),
    apiKeyCleanupRefs: z.array(z.string()).default([]).volatile(),
    poolCooldownMs: z.number().step(1).min(0).default(60_000).volatile(),
    poolInvalidKeyCooldownMs: z.number().step(1).min(0).default(1_800_000).volatile(),
    baseURL: z.string().default('https://api.cline.bot/api/v1').volatile(),
    defaultMaxTokens: z.number().step(1).min(1).default(32_768).volatile(),
    defaultContextWindow: z.number().step(1).min(1).default(262_144).volatile(),
    maxRequestImageBytes: z.number().step(1).min(1).max(Number.MAX_SAFE_INTEGER).default(DEFAULT_MAX_REQUEST_IMAGE_BYTES).volatile(),
    requestImageMaxBytes: z.number().step(1).min(1).max(Number.MAX_SAFE_INTEGER).default(DEFAULT_REQUEST_IMAGE_MAX_BYTES).volatile(),
    retryPolicy: RetryPolicySchema.volatile(),
});

function readField(field) {
    return typeof field?.get === 'function' ? field.get() : field;
}

function liveConfig(config) {
    return structuredClone({
        apiKeyEnv: readField(config?.apiKeyEnv) ?? 'CLINE_API_KEY',
        apiKeyEnvPool: readField(config?.apiKeyEnvPool) ?? [],
        apiKeyCleanupRefs: readField(config?.apiKeyCleanupRefs) ?? [],
        poolCooldownMs: readField(config?.poolCooldownMs) ?? 60_000,
        poolInvalidKeyCooldownMs: readField(config?.poolInvalidKeyCooldownMs) ?? 1_800_000,
        baseURL: readField(config?.baseURL) ?? 'https://api.cline.bot/api/v1',
        defaultMaxTokens: readField(config?.defaultMaxTokens) ?? 32_768,
        defaultContextWindow: readField(config?.defaultContextWindow) ?? 262_144,
        maxRequestImageBytes: readField(config?.maxRequestImageBytes) ?? DEFAULT_MAX_REQUEST_IMAGE_BYTES,
        requestImageMaxBytes: readField(config?.requestImageMaxBytes) ?? DEFAULT_REQUEST_IMAGE_MAX_BYTES,
        retryPolicy: readField(config?.retryPolicy),
    });
}

function isRecord(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function positiveNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined;
}
async function fetchJson(url, timeoutMs, label, fetchImpl = fetch) {
    const response = await fetchImpl(url, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(timeoutMs) });
    if (!response.ok)
        throw new Error(`${label} endpoint answered HTTP ${response.status}`);
    return await response.json();
}
export async function fetchFreeModels(url = 'https://api.cline.bot/api/v1/ai/cline/models', fetchImpl = fetch, freeBucketIds = new Set()) {
    const payload = await fetchJson(url, 30_000, 'Cline models', fetchImpl);
    if (!isRecord(payload) || !Array.isArray(payload.data)) {
        throw new Error('Cline models endpoint returned an unexpected shape');
    }
    const feedIds = new Set();
    for (const raw of payload.data) {
        if (isRecord(raw) && typeof raw.id === 'string')
            feedIds.add(raw.id);
    }
    const freeFeedIds = new Set();
    for (const id of feedIds) {
        if (id.endsWith(':free') || EXTRA_FREE_MODEL_IDS.has(id))
            freeFeedIds.add(id);
    }
    for (const bucketId of freeBucketIds) {
        if (feedIds.has(bucketId)) {
            freeFeedIds.add(bucketId);
            continue;
        }
        const slug = bucketId.split('/').at(-1);
        if (slug === undefined)
            continue;
        const matches = [...feedIds].filter(id => id.split('/').at(-1) === slug);
        if (matches.length === 1)
            freeFeedIds.add(matches[0]);
    }
    const models = [];
    for (const raw of payload.data) {
        if (!isRecord(raw) || typeof raw.id !== 'string')
            continue;
        if (!freeFeedIds.has(raw.id))
            continue;
        const name = typeof raw.name === 'string' && raw.name.length > 0 ? raw.name : undefined;
        const contextWindow = positiveNumber(raw.context_length);
        const maxTokens = positiveNumber(isRecord(raw.top_provider) ? raw.top_provider.max_completion_tokens : undefined);
        const supportedParameters = Array.isArray(raw.supported_parameters)
            ? raw.supported_parameters.filter((x) => typeof x === 'string')
            : undefined;
        const architecture = isRecord(raw.architecture) ? raw.architecture : undefined;
        const imageInput = architecture !== undefined && Array.isArray(architecture.input_modalities)
            && architecture.input_modalities.includes('image');
        models.push({
            id: raw.id,
            ...(name === undefined ? {} : { name }),
            ...(contextWindow === undefined ? {} : { contextWindow }),
            ...(maxTokens === undefined ? {} : { maxTokens }),
            ...(supportedParameters?.includes('reasoning_effort') ? { supportsReasoningEffort: true } : {}),
            ...(imageInput ? { imageInput: true } : {}),
        });
    }
    models.sort((a, b) => a.id.localeCompare(b.id));
    return models;
}
export async function fetchFreeModelIds(url = 'https://api.cline.bot/api/v1/ai/cline/recommended-models', fetchImpl = fetch) {
    const payload = await fetchJson(url, 30_000, 'Cline recommended models', fetchImpl);
    if (!isRecord(payload) || !Array.isArray(payload.free)) {
        throw new Error('Cline recommended-models endpoint returned an unexpected shape');
    }
    const ids = new Set();
    for (const entry of payload.free) {
        if (isRecord(entry) && typeof entry.id === 'string' && entry.id.length > 0)
            ids.add(entry.id);
    }
    return ids;
}
export async function fetchOpenRouterReasoning(url = 'https://openrouter.ai/api/v1/models', fetchImpl = fetch) {
    const payload = await fetchJson(url, 300_000, 'OpenRouter models', fetchImpl);
    if (!isRecord(payload) || !Array.isArray(payload.data)) {
        throw new Error('OpenRouter models endpoint returned an unexpected shape');
    }
    const byId = new Map();
    for (const raw of payload.data) {
        if (!isRecord(raw) || typeof raw.id !== 'string')
            continue;
        const r = isRecord(raw.reasoning) ? raw.reasoning : undefined;
        if (r === undefined)
            continue;
        const efforts = Array.isArray(r.supported_efforts)
            ? r.supported_efforts.filter((x) => typeof x === 'string')
            : undefined;
        if (efforts === undefined || efforts.length === 0)
            continue;
        byId.set(raw.id, {
            supportedEfforts: efforts,
            ...typeof r.mandatory === 'boolean' ? { mandatory: r.mandatory } : {},
        });
    }
    return byId;
}
function reasoningLevelsFor(model) {
    if (!model.supportsReasoningEffort)
        return [];
    const efforts = model.reasoning?.supportedEfforts;
    if (efforts === undefined || efforts.length === 0)
        return [];
    return efforts;
}
const PI_LEVEL_KEYS = ['minimal', 'low', 'medium', 'high', 'xhigh', 'max'];
function reasoningMapFor(levels, mandatory) {
    const map = {};
    for (const key of PI_LEVEL_KEYS) {
        map[key] = levels.includes(key) ? key : null;
    }
    map.off = mandatory ? null : 'none';
    return map;
}
function buildModels(scanned, baseURL, config) {
    return scanned.map(model => {
        const levels = reasoningLevelsFor(model);
        const mandatory = model.reasoning?.mandatory;
        const controllable = levels.length > 0;
        return {
            id: model.id,
            name: model.name ?? model.id,
            api: 'openai-completions',
            provider: PROVIDER,
            baseUrl: baseURL,
            headers: {
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
            input: model.imageInput ? ['text', 'image'] : ['text'],
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
            compat: { requiresReasoningContentOnAssistantMessages: false },
            contextWindow: model.contextWindow ?? config.defaultContextWindow ?? 262_144,
            maxTokens: model.maxTokens ?? config.defaultMaxTokens ?? 32_768,
            ...(controllable ? { thinkingLevelMap: reasoningMapFor(levels, mandatory) } : {}),
        };
    });
}
const normalizeReasoningContext = (context) => ({
    ...context,
    messages: context.messages.map(message => message.role !== 'assistant' ? message : {
        ...message,
        content: message.content.map(block => block.type === 'thinking' && block.thinking.trim().length > 0 && block.thinkingSignature === undefined
            ? { ...block, thinkingSignature: 'reasoning_content' }
            : block),
    }),
});
const rewriteRefusalMessage = (errorMessage) => {
    const start = errorMessage.indexOf('{');
    const end = errorMessage.lastIndexOf('}');
    if (start < 0 || end <= start)
        return errorMessage;
    let parsed;
    try {
        parsed = JSON.parse(errorMessage.slice(start, end + 1));
    }
    catch {
        return errorMessage;
    }
    if (!isRecord(parsed))
        return errorMessage;
    const detail = parsed.type === 'error' && isRecord(parsed.error) ? parsed.error : parsed;
    const message = [detail.message, isRecord(detail.error) ? detail.error.message : undefined, detail.detail]
        .find((value) => typeof value === 'string');
    if (message === undefined)
        return errorMessage;
    const type = typeof detail.type === 'string' ? detail.type : 'Error';
    const code = typeof detail.code === 'string' ? detail.code : '';
    if (AUTH_ERROR_TYPES.has(type) || AUTH_ERROR_TYPES.has(code))
        return errorMessage;
    return `[cline ${type}] ${message}`;
};
const PI_AUTH = {
    credentials: {
        read: async () => undefined,
        list: async () => [],
        modify: async (_providerId, mutate) => mutate(undefined),
        delete: async () => { },
    },
    authContext: { env: async () => undefined, fileExists: async () => false },
};
const sanitizeStream = (stream) => {
    const originalPush = stream.push.bind(stream);
    stream.push = (event) => {
        if (isRecord(event) && event.type === 'error' && isRecord(event.error) && typeof event.error.errorMessage === 'string') {
            event.error.errorMessage = rewriteRefusalMessage(event.error.errorMessage);
        }
        originalPush(event);
    };
    return stream;
};
const CLINE_VALID_EFFORTS = new Set(['max', 'xhigh', 'high', 'medium', 'low', 'minimal', 'none']);
function sanitizePayload(params, explicitReasoning) {
    if (typeof params.reasoning_effort === 'string') {
        if (explicitReasoning === undefined) {
            delete params.reasoning_effort;
        }
        else if (params.reasoning_effort === 'off') {
            params.reasoning_effort = 'none';
        }
        else if (!CLINE_VALID_EFFORTS.has(params.reasoning_effort)) {
            delete params.reasoning_effort;
        }
    }
}
function withPayloadSanitization(options, explicitReasoning) {
    const customOnPayload = options?.onPayload;
    return {
        ...options,
        onPayload: async (params, model) => {
            let current = params;
            if (customOnPayload) {
                current = (await customOnPayload(params, model)) ?? params;
            }
            if (isRecord(current)) {
                sanitizePayload(current, explicitReasoning);
            }
            return current;
        },
    };
}
const CLINE_USER_AGENT = 'Cline/3.0.47';
const clineFetchWithUserAgent = (baseUrl, inner) => {
    let host;
    try {
        host = new URL(baseUrl).host;
    }
    catch {
        host = undefined;
    }
    const native = inner ?? globalThis.fetch;
    if (host === undefined)
        return native;
    return (input, init) => {
        const url = typeof input === 'string'
            ? input
            : input instanceof URL ? input.href : input instanceof Request ? input.url : String(input);
        if (!url.includes(host))
            return native(input, init);
        const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
        headers.set('user-agent', CLINE_USER_AGENT);
        return native(input, { ...init, headers });
    };
};

// ---- MetaMath 多 Key 轮询与故障转移池（GOAL-81 / GOAL-84 M02-M03） ----
const baseApi = openAICompletionsApi();
function isRetryableKeyError(message) {
    return /\b(401|403|429)\b/.test(message)
        || /unauthorized|invalid[ _-]?api[ _-]?key|quota|rate[ _-]?limit|insufficient|too many requests/i.test(message);
}
function errorMessageOf(event) {
    if (isRecord(event) && isRecord(event.error) && typeof event.error.errorMessage === 'string') {
        return event.error.errorMessage;
    }
    return String(event);
}
function isKeyInvalidMessage(message) {
    return /\b401\b/.test(message) || /unauthorized|invalid[ _-]?api[ _-]?key/i.test(message);
}
function makeAttempt(kind, model, context, options, apiKey) {
    const explicitReasoning = kind === 'stream'
        ? (isRecord(options) ? options.reasoningEffort : undefined)
        : options?.reasoning;
    const withKey = {
        ...options,
        fetch: clineFetchWithUserAgent(model.baseUrl, options?.fetch),
        ...(apiKey === undefined ? {} : { apiKey }),
    };
    const inner = kind === 'stream'
        ? baseApi.stream(model, normalizeReasoningContext(context), withPayloadSanitization(withKey, explicitReasoning))
        : baseApi.streamSimple(model, normalizeReasoningContext(context), withPayloadSanitization(withKey, explicitReasoning));
    return sanitizeStream(inner);
}
const CONTENT_EVENT_TYPES = new Set([
    'text_delta',
    'thinking_delta',
    'toolcall_start',
    'toolcall_delta',
    'toolcall_end',
]);
export function failoverStream(kind, pool, model, context, options, attempt = makeAttempt) {
    const outer = createAssistantMessageEventStream();
    const signal = options?.signal;
    const cancel = () => {
        outer.push({
            type: 'error', reason: 'aborted', error: {
                role: 'assistant', api: 'openai-completions', provider: PROVIDER,
                model: model.id ?? 'unknown', stopReason: 'aborted',
                errorMessage: 'Request aborted', content: [],
            },
        });
        outer.end();
    };
    if (signal?.aborted) { cancel(); return outer; }
    signal?.addEventListener('abort', cancel, { once: true });
    void (async () => {
        try {
            if (!pool.enabled()) {
                for await (const event of attempt(kind, model, context, options, undefined)) {
                    if (signal?.aborted) return;
                    outer.push(event);
                    if (event.type === 'error' || event.type === 'done') return;
                }
                outer.end();
                return;
            }
            const keys = await pool.usableKeys();
            if (signal?.aborted) return;
            if (keys.length === 0) {
                outer.push({
                    type: 'error', reason: 'error', error: {
                        role: 'assistant', api: 'openai-completions', provider: PROVIDER,
                        model: 'unknown', stopReason: 'error',
                        errorMessage: 'cline-free-provider: every pool key is cooling down or missing; add keys on the Cline Free API Key card or wait out the cooldown',
                        content: [],
                    },
                });
                outer.end();
                return;
            }
            let contentSeen = false;
            let lastError = undefined;
            for (let attemptIndex = 0; attemptIndex < keys.length; attemptIndex++) {
                if (signal?.aborted) return;
                const key = keys[attemptIndex];
                let switched = false;
                for await (const event of attempt(kind, model, context, options, key)) {
                    if (signal?.aborted) return;
                    if (event.type === 'error') {
                        const message = errorMessageOf(event);
                        if (isRetryableKeyError(message)) {
                            const ms = isKeyInvalidMessage(message) ? pool.invalidCooldownMs() : pool.cooldownMs();
                            pool.cool(key, ms);
                            if (!contentSeen && attemptIndex < keys.length - 1) {
                                pool.warn(`key #${attemptIndex + 1} failed, failing over to the next pool key`);
                                switched = true;
                                break;
                            }
                        }
                        lastError = event;
                        break;
                    }
                    if (CONTENT_EVENT_TYPES.has(event.type)
                        && (!(event.type === 'text_delta' || event.type === 'thinking_delta') || event.delta.length > 0)) {
                        contentSeen = true;
                    }
                    outer.push(event);
                    if (event.type === 'done') return;
                }
                if (!switched) {
                    if (lastError !== undefined) outer.push(lastError);
                    outer.end();
                    return;
                }
            }
            outer.push(lastError ?? {
                type: 'error', reason: 'error', error: {
                    role: 'assistant', api: 'openai-completions', provider: PROVIDER,
                    model: 'unknown', stopReason: 'error',
                    errorMessage: 'cline-free-provider: all pool keys failed',
                    content: [],
                },
            });
            outer.end();
        }
        catch (error) {
            if (signal?.aborted) return;
            outer.push({
                type: 'error', reason: 'error', error: {
                    role: 'assistant', api: 'openai-completions', provider: PROVIDER,
                    model: 'unknown', stopReason: 'error',
                    errorMessage: `cline-free-provider: key pool failure: ${errorChain(error)}`,
                    content: [],
                },
            });
            outer.end();
        }
        finally {
            signal?.removeEventListener('abort', cancel);
        }
    })();
    return outer;
}
function createApi(pool) {
    return {
        stream: (model, context, options) => failoverStream('stream', pool, model, context, options),
        streamSimple: (model, context, options) => failoverStream('streamSimple', pool, model, context, options),
    };
}
function poolRefs(opts) {
    return [opts.apiKeyEnv ?? 'CLINE_API_KEY', ...(opts.apiKeyEnvPool ?? [])];
}
export function createKeyPool(ctx, current) {
    const KEY_CACHE_TTL_MS = 60_000;
    const keyCache = { at: 0, entries: [] };
    const cooldownUntil = new Map();
    let cursor = 0;
    const isPoolMode = (opts) => (opts.apiKeyEnvPool ?? []).length > 0;
    async function loadKeys(opts) {
        const now = Date.now();
        if (keyCache.at !== 0 && now - keyCache.at < KEY_CACHE_TTL_MS)
            return keyCache.entries;
        const credentials = ctx.get('credentials');
        const entries = [];
        for (const rawRef of new Set(poolRefs(opts))) {
            const ref = String(rawRef);
            let value;
            if (credentials !== undefined) {
                const hit = await credentials.resolve(credentialRef(ref));
                value = hit?.value;
            }
            else {
                const ambient = launchEnvironmentOf(ctx).get(ref);
                value = ambient !== undefined && ambient.value.length > 0 ? ambient.value : undefined;
            }
            if (value !== undefined && value.length > 0)
                entries.push({ ref, value });
        }
        keyCache.at = now;
        keyCache.entries = entries;
        return entries;
    }
    return {
        enabled: () => isPoolMode(current()),
        cooldownMs: () => current().poolCooldownMs ?? 60_000,
        invalidCooldownMs: () => current().poolInvalidKeyCooldownMs ?? 1_800_000,
        cool: (key, ms) => {
            cooldownUntil.set(key, Date.now() + ms);
            keyCache.at = 0;
        },
        usableKeys: async () => {
            const now = Date.now();
            const entries = (await loadKeys(current())).filter(entry => (cooldownUntil.get(entry.value) ?? 0) <= now);
            if (entries.length === 0) return [];
            const rotated = [];
            for (let i = 0; i < entries.length; i++) {
                rotated.push(entries[(cursor + i) % entries.length].value);
            }
            cursor += 1;
            return rotated;
        },
        peekUsableKeys: async () => {
            const now = Date.now();
            const entries = (await loadKeys(current())).filter(entry => (cooldownUntil.get(entry.value) ?? 0) <= now);
            if (entries.length === 0) return [];
            const rotated = [];
            for (let i = 0; i < entries.length; i++) {
                rotated.push(entries[(cursor + i) % entries.length].value);
            }
            return rotated;
        },
        warn: (message) => {
            ctx.logger.warn('[%s] %s', name, message);
        },
        invalidateCache: () => {
            keyCache.at = 0;
        },
    };
}

export async function apply(ctx, config) {
    const settingsNs = ctx.fiber?.entry?.options?.id ?? name;
    let scanned = [];
    const pool = createKeyPool(ctx, () => liveConfig(config));
    const api = createApi(pool);
    const buildProfiles = () => {
        const opts = liveConfig(config);
        const baseURL = opts.baseURL ?? 'https://api.cline.bot/api/v1';
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
        });
        return new Map([
            [
                PROVIDER,
                {
                    provider: PROVIDER,
                    displayName: DISPLAY_NAME,
                    apiKeyEnv: credentialRef(opts.apiKeyEnv ?? 'CLINE_API_KEY'),
                    streamIdleTimeoutMs: 300_000,
                    maxRequestImageBytes: opts.maxRequestImageBytes ?? DEFAULT_MAX_REQUEST_IMAGE_BYTES,
                    requestImagePixelBudget: 4_194_304,
                    requestImageMaxBytes: opts.requestImageMaxBytes ?? DEFAULT_REQUEST_IMAGE_MAX_BYTES,
                    retryPolicy: resolveRetryPolicy(opts.retryPolicy, 'cline-free-provider: retryPolicy'),
                    piProvider,
                    modelErrors: new Map(),
                    configuredMaxTokens: new Map(),
                },
            ],
        ]);
    };
    let profiles = buildProfiles();
    const adapter = new PiAiAdapter({
        resolveAttachments: () => ctx.get('attachments'),
        profiles: () => profiles,
        auth: PI_AUTH,
        resolveApiKey: async (provider, profile) => {
            if (pool.enabled()) {
                const keys = await pool.peekUsableKeys();
                if (keys.length === 0) {
                    const refs = poolRefs(liveConfig(config)).map(String).join(', ');
                    throw new LlmError(`cline-free-provider: every pool key is missing or cooling down (${refs}); add keys on the Cline Free API Key card or wait out the cooldown`, 'MISSING_CREDENTIAL');
                }
                return keys[0];
            }
            const ref = profile.apiKeyEnv;
            if (ref === undefined)
                return undefined;
            const credentials = ctx.get('credentials');
            if (credentials !== undefined) {
                const hit = await credentials.resolve(ref);
                if (hit !== undefined)
                    return assertUsableApiKey(hit.value, 'cline-free-provider', String(ref));
            }
            else {
                const ambient = launchEnvironmentOf(ctx).get(String(ref));
                if (ambient !== undefined && ambient.value.length > 0) {
                    return assertUsableApiKey(ambient.value, 'cline-free-provider', String(ref));
                }
            }
            throw new LlmError(`cline-free-provider: no API key for provider route "${provider}"; store ${String(ref)} through the credentials`
                + ` service (the web Models page writes it), or export ${String(ref)} in the launching environment`, 'MISSING_CREDENTIAL');
        },
    });
    ctx.llm.registerConfigurableProviders([
        { provider: PROVIDER, displayName: DISPLAY_NAME, settingsNs, settingsPath: [] },
    ]);
    ctx.llm.registerAdapter([PROVIDER], adapter);
    ctx.on('loader/volatile-update', () => {
        pool.invalidateCache();
        profiles = buildProfiles();
    });
    async function sync() {
        const freeBucketIds = await fetchFreeModelIds().catch((error) => {
            ctx.logger.warn('[%s] recommended-models scan failed; falling back to suffix+extra list: %s', name, errorChain(error));
            return new Set();
        });
        const [entries, reasoningById] = await Promise.all([
            fetchFreeModels('https://api.cline.bot/api/v1/ai/cline/models', fetch, freeBucketIds),
            fetchOpenRouterReasoning().catch((error) => {
                ctx.logger.warn('[%s] OpenRouter reasoning scan failed; falling back to Cline-only metadata: %s', name, errorChain(error));
                return new Map();
            }),
        ]);
        const next = entries.map(entry => ({
            ...entry,
            ...(reasoningById.has(entry.id) ? { reasoning: reasoningById.get(entry.id) } : {}),
        }));
        if (next.length === 0) {
            throw new Error('no free models found; keeping the previous catalog');
        }
        if (deepEqualJson(next, scanned))
            return;
        scanned = next;
        profiles = buildProfiles();
        ctx.logger.info('[%s] synced %d free model(s): %s', name, scanned.length, scanned.map(m => m.id).join(', '));
    }
    void sync().catch((error) => {
        ctx.logger.warn('[%s] initial catalog scan failed: %s', name, errorChain(error));
    });
}
