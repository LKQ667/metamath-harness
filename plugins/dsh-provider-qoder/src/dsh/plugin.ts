/** Register the Qoder subscription provider with DSH. */

import type { Context, FiberState } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-connection'
import type {} from '@deepseek-ai/dsh-attachment'
import type {} from '@deepseek-ai/dsh-web'
import type { ConnectionRpcHandler } from '@deepseek-ai/dsh-client-connection'
import type { SettingsNamespace } from '@deepseek-ai/dsh-settings'
import { QoderAdapter } from './adapter.ts'
import { QODER_PROVIDER_ID } from './provider.ts'
import { QoderSearchProvider } from './search-provider.ts'
import {
  hasSameQoderDiscoveryMetadata,
  mergeQoderDiscoveryMetadata,
  type QoderCatalogModel,
} from '../qoder/catalog.ts'
import { resolveManagedQoderPat } from './credential.ts'
import type { QoderRegion } from '../qoder/region.ts'
import { QoderLlmError } from '../qoder/errors.ts'
import {
  createQoderTransport,
  defaultResponseHeaderTimeoutMs,
  defaultStreamIdleTimeoutMs,
  type QoderTransport,
  type QoderTransportOptions,
} from '../qoder/transport/index.ts'
import { Config, modelsFor, resolveModels, type Config as QoderConfig } from './config.ts'
import { isQoderRpcEndpoint, type QoderRpcErrorCode } from './rpc-channel.ts'
import { registerQoderRpc } from './rpc.ts'

export const name = 'provider-qoder'
export const inject = ['llm', 'credentials', 'connection', 'attachments']

const providerQoder = QODER_PROVIDER_ID
const settingsNamespace = 'provider-qoder' as SettingsNamespace
const fiberDisposed: FiberState = 4
const fiberUnloading: FiberState = 5

type QoderLogger = NonNullable<QoderTransportOptions['logger']>

function logError(error: unknown): unknown {
  if (!(error instanceof Error)) return { name: 'UnknownError' }
  return {
    name: error.name,
    message: error.message,
    ...'code' in error ? { code: error.code } : {},
  }
}

type QoderHostRpcResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: { readonly code: QoderRpcErrorCode; readonly message: string; readonly details: object } }

function publicError(code: QoderRpcErrorCode, message: string, details: object = { issues: [] }): QoderHostRpcResult<never> {
  return {
    ok: false,
    error: { code, message, details },
  }
}

export function apply(ctx: Context, config: QoderConfig = {}): void {
  const logger = (ctx as Context & { logger?: QoderLogger }).logger
  const initialRegion = config.region ?? 'global'
  const hasConfiguredModels = config.models !== undefined && config.models.length > 0
  const baseConfig: QoderConfig = {
    region: initialRegion,
    modelsByRegion: { ...config.modelsByRegion },
    ...hasConfiguredModels ? { models: resolveModels(config.models) } : {},
    streamIdleTimeoutMs: config.streamIdleTimeoutMs ?? defaultStreamIdleTimeoutMs,
    responseHeaderTimeoutMs: config.responseHeaderTimeoutMs ?? defaultResponseHeaderTimeoutMs,
    preserveThinking: config.preserveThinking ?? true,
    webSearchMode: config.webSearchMode ?? 'auto',
  }
  let current = (): QoderConfig => baseConfig
  let legacyModelsRegion = initialRegion
  let persistDiscoveredModels = async (_region: QoderRegion): Promise<void> => {}
  const discoveredCatalogs: Record<QoderRegion, readonly QoderCatalogModel[]> = {
    global: [],
    china: [],
  }

  const createTransport = (
    region: QoderRegion,
    streamIdleTimeoutMs: number,
    responseHeaderTimeoutMs: number,
    preserveThinking: boolean,
    resolvePat: () => Promise<string> = () => resolveManagedQoderPat(ctx.credentials),
  ): QoderTransport => createQoderTransport({
    region,
    resolvePat,
    logger,
    streamIdleTimeoutMs,
    responseHeaderTimeoutMs,
    attachments: ctx.attachments,
    preserveThinking,
  })

  const resolveConfig = () => {
    const value = current()
    const region = value.region ?? 'global'
    return {
      region,
      models: mergeQoderDiscoveryMetadata(
        modelsFor(value, region, legacyModelsRegion),
        discoveredCatalogs[region],
      ),
      streamIdleTimeoutMs: value.streamIdleTimeoutMs ?? defaultStreamIdleTimeoutMs,
      responseHeaderTimeoutMs: value.responseHeaderTimeoutMs ?? defaultResponseHeaderTimeoutMs,
      preserveThinking: value.preserveThinking ?? true,
      webSearchMode: value.webSearchMode ?? 'auto',
    }
  }

  const initial = resolveConfig()
  let activeTransport = createTransport(
    initial.region,
    initial.streamIdleTimeoutMs,
    initial.responseHeaderTimeoutMs,
    initial.preserveThinking,
  )
  let activeTransportConfig = {
    region: initial.region,
    streamIdleTimeoutMs: initial.streamIdleTimeoutMs,
    responseHeaderTimeoutMs: initial.responseHeaderTimeoutMs,
    preserveThinking: initial.preserveThinking,
  }
  const adapter = new QoderAdapter({
    resolveTransport: () => activeTransport,
    models: initial.models,
    providerId: providerQoder,
    providerName: 'Qoder',
  })

  const registration = ctx.llm.registerAdapter([providerQoder], adapter)
  const refreshAdapter = (): void => {
    const next = resolveConfig()
    if (next.region !== activeTransportConfig.region
      || next.streamIdleTimeoutMs !== activeTransportConfig.streamIdleTimeoutMs
      || next.responseHeaderTimeoutMs !== activeTransportConfig.responseHeaderTimeoutMs
      || next.preserveThinking !== activeTransportConfig.preserveThinking) {
      activeTransport = createTransport(
        next.region,
        next.streamIdleTimeoutMs,
        next.responseHeaderTimeoutMs,
        next.preserveThinking,
      )
      activeTransportConfig = {
        region: next.region,
        streamIdleTimeoutMs: next.streamIdleTimeoutMs,
        responseHeaderTimeoutMs: next.responseHeaderTimeoutMs,
        preserveThinking: next.preserveThinking,
      }
    }
    adapter.replaceModels(next.models)
    registration.replace([providerQoder])
  }

  ctx.inject(['settings'], (settingsCtx) => {
    const scope = settingsCtx.settings.register(settingsNamespace, Config, {
      base: baseConfig,
      validate: (value) => {
        for (const region of Object.keys(value.modelsByRegion ?? {})) {
          if (region !== 'global' && region !== 'china') {
            throw new Error(`provider-qoder: unsupported model catalog region "${region}"`)
          }
        }
        modelsFor(value, 'global', legacyModelsRegion)
        modelsFor(value, 'china', legacyModelsRegion)
      },
    })
    legacyModelsRegion = scope.get().region ?? initialRegion
    current = () => scope.get()
    persistDiscoveredModels = async (region) => {
      const value = scope.get()
      const selected = modelsFor(value, region, legacyModelsRegion)
      const enriched = mergeQoderDiscoveryMetadata(selected, discoveredCatalogs[region])
      if (!hasSameQoderDiscoveryMetadata(selected, enriched)) {
        await scope.update({ modelsByRegion: { ...value.modelsByRegion, [region]: enriched } })
      }
    }
    refreshAdapter()

    const loaded = scope.get()
    const loadedRegion = loaded.region ?? 'global'
    if (loaded.models !== undefined && loaded.models.length > 0
      && loaded.modelsByRegion?.[loadedRegion] === undefined) {
      void scope.update({
        modelsByRegion: {
          ...loaded.modelsByRegion,
          [loadedRegion]: resolveModels(loaded.models),
        },
      }).catch(error => logger?.error?.('[Qoder Settings] Failed to migrate model catalog', logError(error)))
    }

    scope.watch(async (next) => {
      if (ctx.fiber.state === fiberUnloading || ctx.fiber.state === fiberDisposed) return
      refreshAdapter()
      const region = next.region ?? 'global'
      const selected = modelsFor(next, region, legacyModelsRegion)
      const enriched = mergeQoderDiscoveryMetadata(selected, discoveredCatalogs[region])
      if (!hasSameQoderDiscoveryMetadata(selected, enriched)) {
        await scope.update({
          modelsByRegion: { ...next.modelsByRegion, [region]: enriched },
        })
      }
    })
    settingsCtx.effect(() => () => {
      if (ctx.fiber.state === fiberUnloading || ctx.fiber.state === fiberDisposed) return
      persistDiscoveredModels = async () => {}
      current = () => baseConfig
      refreshAdapter()
    })
  })

  const discoverModels = async (signal?: AbortSignal, suppliedPat?: string): Promise<readonly QoderCatalogModel[]> => {
    const snapshot = resolveConfig()
    const snapshotTransport = activeTransport
    const normalizedPat = suppliedPat?.trim()
    const transport = normalizedPat
      ? createTransport(
          snapshot.region,
          snapshot.streamIdleTimeoutMs,
          snapshot.responseHeaderTimeoutMs,
          snapshot.preserveThinking,
          () => Promise.resolve(normalizedPat),
        )
      : snapshotTransport
    const models = await transport.discoverModels(signal)
    adapter.updateDiscoveredModels(snapshotTransport, models)
    discoveredCatalogs[snapshot.region] = models
    refreshAdapter()
    await persistDiscoveredModels(snapshot.region)
    return models
  }

  ctx.llm.registerModelDiscovery(settingsNamespace, async (request, signal) => {
    if (request.provider !== undefined && request.provider !== providerQoder) {
      throw new QoderLlmError(`Qoder discovery does not own provider "${request.provider}".`, 'INVALID_PROVIDER')
    }
    return (await discoverModels(signal, request.apiKey)).map(model => ({
      id: model.id,
      name: model.name,
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens,
    }))
  })

  const handler: ConnectionRpcHandler = async (endpoint, payload, signal) => {
    if (!isQoderRpcEndpoint(endpoint)) return publicError('UNKNOWN_ENDPOINT', `Unknown endpoint: ${endpoint}`)
    if (signal.aborted) return publicError('ABORTED', 'Request aborted')

    const executeRpc = async <T>(operation: string, task: () => Promise<T>): Promise<QoderHostRpcResult<T>> => {
      try {
        return { ok: true, value: await task() }
      } catch (error) {
        if (signal.aborted || (error instanceof QoderLlmError && error.code === 'ABORTED')) {
          logger?.debug?.(`[Qoder RPC] ${operation} was aborted`)
          return publicError('ABORTED', 'Request aborted')
        }
        let code: QoderRpcErrorCode = 'INTERNAL'
        if (error instanceof QoderLlmError) {
          if (error.code === 'MISSING_CREDENTIAL' || error.code === 'NO_CREDENTIALS') {
            code = 'NO_CREDENTIALS'
          } else if (error.code === 'AUTH') {
            code = 'UNAUTHENTICATED'
          } else if (error.code === 'TIMEOUT') {
            code = 'TIMEOUT'
          } else {
            code = 'UPSTREAM_ERROR'
          }
        }
        logger?.error?.(`[Qoder RPC] Failed to ${operation}`, logError(error))
        return publicError(code, error instanceof Error ? error.message : `Failed to ${operation}`)
      }
    }

    if (endpoint === 'models') {
      return await executeRpc('discover Qoder models', () => discoverModels(signal))
    }

    const force = typeof payload === 'object' && payload !== null && 'force' in payload
      ? payload.force === true
      : false
    logger?.debug?.('[Qoder RPC] Reading subscriber account', { force })
    const outcome = await executeRpc(
      'load Qoder account',
      () => activeTransport.readAccount({ force, signal }),
    )
    if (outcome.ok) logger?.debug?.('[Qoder RPC] Subscriber account resolved')
    return outcome
  }

  try {
    ctx.effect(() => registerQoderRpc(ctx, handler), 'provider-qoder: settings RPC routes')
  } catch (error) {
    // The settings RPC is an optional surface: a registration failure must not
    // take the model adapter or the web-search router down with it.
    logger?.error?.('[Qoder RPC] Failed to register the settings RPC routes', logError(error))
  }

  ctx.inject(['web'], (webCtx) => {
    const searchProvider = new QoderSearchProvider({
      ctx,
      resolveTransport: () => activeTransport,
      getWebSearchMode: () => resolveConfig().webSearchMode ?? 'auto',
    })
    webCtx.web.registerSearchProvider(searchProvider)

    // Transparent interceptor: ensure that when a Qoder model is active,
    // ctx.web.search always routes to Qoder even if the host profile configured
    // a different fixed searchProvider (e.g. deepseek-official).
    if (typeof webCtx.web.search === 'function') {
      const originalSearch = webCtx.web.search.bind(webCtx.web)
      webCtx.effect(() => {
        webCtx.web.search = async (request, signal) => {
          const mode = resolveConfig().webSearchMode ?? 'auto'
          if (mode === 'disabled') {
            return originalSearch(request, signal)
          }

          const agentsService = ctx.get('agents')
            ?? (ctx as unknown as { agents?: { currentInitiator?: () => { options?: { provider?: string } } } }).agents
          const agent = agentsService?.currentInitiator?.()
          const defaultModelService = ctx.get('agentDefaultModel') as unknown as { get?: () => { provider?: string } }
          const providerRoute = agent?.options?.provider ?? defaultModelService?.get?.()?.provider
          const isQoderActive = providerRoute === providerQoder

          if (mode === 'always' || isQoderActive) {
            return searchProvider.search(request, signal)
          }

          return originalSearch(request, signal)
        }
        return () => {
          webCtx.web.search = originalSearch
        }
      }, 'provider-qoder: transparent web search router')
    }
  })
}
