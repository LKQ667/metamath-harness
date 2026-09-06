import { createProvider } from '@earendil-works/pi-ai'
import type { Api, AuthContext, CredentialStore, Model, Provider } from '@earendil-works/pi-ai'
import { openAICompletionsApi } from '@earendil-works/pi-ai/api/openai-completions.lazy'
import { resolveRetryPolicy } from '@deepseek-ai/dsh-llm'
import { PiAiAdapter } from '@deepseek-ai/dsh-llm-pi-ai'
import type { ResolvedPiAiProviderProfile } from '@deepseek-ai/dsh-llm-pi-ai'
import type { AttachmentStore } from '@deepseek-ai/dsh-attachment'
import { traeInputModalities, type TraeCatalog, type TraeModelInfo } from './catalog.ts'
import type { TraeShim } from './shim.ts'

export const TRAE_PROVIDER = 'trae'
export const TRAE_STREAM_IDLE_TIMEOUT_MS = 300_000

const INERT_AUTH: { credentials: CredentialStore; authContext: AuthContext } = {
  credentials: {
    async read() { return undefined },
    async list() { return [] },
    async modify() { throw new Error('dsh-connect-trae has no pi-ai credential lifecycle') },
    async delete() {},
  },
  authContext: {
    async env() { return undefined },
    async fileExists() { return false },
  },
}

const REQUEST_IMAGE_BUDGETS = {
  maxRequestImageBytes: 20_971_520,
  requestImagePixelBudget: 4_194_304,
  requestImageMaxBytes: 1_048_576,
} as const

function toPiModel(info: TraeModelInfo, baseUrl: string): Model<Api> {
  return {
    id: info.id,
    name: info.name,
    api: 'openai-completions',
    provider: TRAE_PROVIDER,
    baseUrl,
    input: traeInputModalities(info),
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    reasoning: info.reasoningEfforts !== undefined,
    ...(info.reasoningEfforts === undefined ? {} : {
      thinkingLevelMap: {
        off: null,
        minimal: null,
        low: info.reasoningEfforts.low ?? null,
        medium: null,
        high: info.reasoningEfforts.high ?? null,
        xhigh: info.reasoningEfforts.xhigh ?? null,
        max: null,
      },
    }),
    ...(info.contextWindow === undefined ? {} : { contextWindow: info.contextWindow }),
    ...(info.maxTokens === undefined ? {} : { maxTokens: info.maxTokens }),
    compat: { supportsReasoningEffort: info.reasoningEfforts !== undefined },
  } as unknown as Model<Api>
}

export interface TraeAdapterOptions {
  shim: TraeShim
  catalog: TraeCatalog
  resolveAttachments?: () => AttachmentStore | undefined
}

export interface TraeAdapter {
  adapter: PiAiAdapter
  invalidate(): void
}

export function createTraeAdapter(options: TraeAdapterOptions): TraeAdapter {
  const buildModels = (): Model<Api>[] => options.catalog.current()
    .map(info => toPiModel(info, `${options.shim.baseUrl()}/v1`))

  const base = createProvider({
    id: TRAE_PROVIDER,
    name: 'Trae',
    auth: {
      apiKey: {
        name: 'Trae loopback secret',
        async resolve({ credential }) {
          const apiKey = credential?.key
          return apiKey === undefined || apiKey.length === 0
            ? undefined
            : { auth: { apiKey }, source: 'Trae loopback' }
        },
      },
    },
    models: buildModels(),
    api: openAICompletionsApi(),
  })
  const provider: Provider = { ...base, getModels: () => buildModels() }
  const profile: ResolvedPiAiProviderProfile = {
    provider: TRAE_PROVIDER,
    displayName: 'Trae',
    streamIdleTimeoutMs: TRAE_STREAM_IDLE_TIMEOUT_MS,
    retryPolicy: resolveRetryPolicy(undefined, 'dsh-connect-trae retryPolicy'),
    configuredMaxTokens: new Map(),
    ...REQUEST_IMAGE_BUDGETS,
    piProvider: provider,
  }
  let profiles = new Map<string, ResolvedPiAiProviderProfile>([[TRAE_PROVIDER, profile]])
  const adapter = new PiAiAdapter({
    profiles: () => profiles,
    auth: INERT_AUTH,
    resolveApiKey: async () => options.shim.token(),
    ...options.resolveAttachments === undefined ? {} : { resolveAttachments: options.resolveAttachments },
  })

  return {
    adapter,
    invalidate() {
      profiles = new Map([[TRAE_PROVIDER, profile]])
    },
  }
}
