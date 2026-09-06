import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import * as dshSettings from '@deepseek-ai/dsh-settings'
import type { SettingsSectionHooks } from '@deepseek-ai/dsh-settings'
import type {} from '@deepseek-ai/dsh-attachment'
import type {} from '@deepseek-ai/dsh-host-webserver'
import { createTraeAdapter, TRAE_PROVIDER } from './adapter.ts'
import { TraeCredentialStore } from './auth.ts'
import { applyImageSelection, deriveCatalog, discoveredCatalog, FALLBACK_TRAE_MODELS, mergeTraeModelSources, sanitizeCatalog, TraeCatalog, traeInputModalities, type TraeModelInfo } from './catalog.ts'
import { refreshTraeCredential } from './refresh.ts'
import { pickTraeStorageIdentity, readTraeIdentity } from './identity.ts'
import { traeStorageCandidates } from './paths.ts'
import { createTraeShim } from './shim.ts'
import { TraeSoloUpstreamClient } from './solo.ts'
import { TraeSoloBridge } from './solo-bridge.ts'
import { TraeSoloRemoteCatalogClient } from './solo-remote.ts'
import { TraeRawChatUpstreamClient } from './raw-upstream.ts'
import { createTraeRawGateway } from './raw-gateway.ts'
import { resolveTraeRawRuntime } from './raw-resolver.ts'
import type { TraeRawDiagnostic } from './raw-diagnostic.ts'
import { TraeDelegatingUpstreamClient } from './delegating-upstream.ts'
import { TraeUsageClient } from './usage.ts'
import { registerTraeUsageRoute } from './web-status.ts'

export { createTraeAdapter, TRAE_PROVIDER, TRAE_STREAM_IDLE_TIMEOUT_MS } from './adapter.ts'
export { normalizeTraeCredential, traeOwnAuthPath, TraeCredentialStore, type TraeCredential } from './auth.ts'
export { applyContextBudgets, applyImageSelection, deriveCatalog, discoveredCatalog, FALLBACK_TRAE_MODELS, mergeTraeModelSources, sanitizeCatalog, TraeCatalog, traeInputModalities, type TraeContextBudget, type TraeInputModality, type TraeModelInfo, type TraeWireModel } from './catalog.ts'
export { decryptTraeStorageValue, parseTraeAuthValue, parseTraeStorageDocument } from './decrypt.ts'
export { identityHeaders, pickTraeStorageIdentity, readTraeIdentity, type TraeIdentity } from './identity.ts'
export { parseObservedModelConfig, type TraeObservedModelConfig } from './model-config.ts'
export { parseTraeCachedModel, readTraeCachedModel, type TraeCachedModelConfig } from './model-cache.ts'
export { parseTraeModelExtraConfigLogLine, parseTraeRawChatBehaviorConfig, type TraeRawChatBehaviorConfig } from './model-extra-config.ts'
export { buildTraeModelDetailRequest, TRAE_MODEL_DETAIL_FUNCTIONS, TRAE_MODEL_DETAIL_PATH, type TraeModelDetailRequest } from './model-detail.ts'
export { parseTraeRemoteModel, type TraeDiscoveredModel, type TraeDiscoveredReasoning } from './model-metadata.ts'
export { traeStorageCandidates, type TraeEdition, type TraeStorageCandidate } from './paths.ts'
export { buildTraeAgentTaskBody, buildTraeCnHeaders, normalizeTraeVersionCode, TRAE_CN_AGENT_TASK_PATH, TRAE_CN_TITLE_PATH, TRAE_VERSION_CODE_FALLBACK, traeEndpoint } from './protocol.ts'
export { buildTraeRawChatDraft, decodeRawChatChunk, TRAE_RAW_CHAT_V1_PATH, TRAE_RAW_CHAT_V2_PATH, type RawChatDelta, type RawChatMessage, type RawChatTool } from './raw-chat.ts'
export { buildTraeFusionRawChatEnvelope, hashTraeRawChatArg, type TraeFusionRawChatEnvelope } from './raw-envelope.ts'
export { buildTraeRawChatRuntimeConfig, traeRawChatExtraInfo, type TraeRawChatRuntimeConfig } from './raw-runtime-config.ts'
export { resolveTraeRawRuntime, type TraeRawResolverResult } from './raw-resolver.ts'
export { rawCapabilityFingerprint } from './raw-fingerprint.ts'
export { rawCapabilityDiagnostic, type TraeRawDiagnostic, type TraeRawDiagnosticState } from './raw-diagnostic.ts'
export { createTraeRawGateway, type TraeRawGateway, type TraeRawGatewayOptions } from './raw-gateway.ts'
export { classifyTraeRawChatFailure, TraeRawChatUpstreamClient, type TraeRawChatClientOptions, type TraeRawChatConfig, type TraeRawChatFailureReason } from './raw-upstream.ts'
export { probeTraeRawChatCapability, type TraeRawChatCapability } from './raw-capability.ts'
export { TraeRawCapabilityState, type TraeRawCapabilitySnapshot } from './raw-capability-state.ts'
export { TraeRawCapabilityController, type TraeRawCapabilityControllerOptions } from './raw-capability-controller.ts'
export { TraeFallbackUpstreamClient, type TraeFallbackUpstreamOptions } from './fallback-upstream.ts'
export { TraeGatedUpstreamClient, type TraeGatedUpstreamOptions } from './gated-upstream.ts'
export { applyReasoningEffort, parseReasoningCapability, TRAE_REASONING_EFFORTS, type TraeReasoningCapability, type TraeReasoningEffort } from './reasoning.ts'
export { refreshTraeCredential } from './refresh.ts'
export { decodeTraeEvent, SseDecoder, type SseEvent, type TraeStreamEvent } from './sse.ts'
export { prepareSoloBody, TraeSoloUpstreamClient, TRAE_SOLO_CHAT_PATH, TRAE_SOLO_FUNCTION, TRAE_SOLO_MODELS_PATH, type TraeSoloClientOptions } from './solo.ts'
export { bridgeTraeSoloStream, TraeSoloBridge } from './solo-bridge.ts'
export { TraeSoloRemoteCatalogClient, TRAE_SOLO_REMOTE_BASE, type TraeSoloRemoteCatalogOptions } from './solo-remote.ts'
export { TraeDelegatingUpstreamClient } from './delegating-upstream.ts'
export { TRAE_PAY_BASE, TraeUsageClient, type TraeActivityRule, type TraeCheckinStatus, type TraeUsageOptions, type TraeUsagePack, type TraeUsageSnapshot, type TraeUsageSummary, type TraeUsageView } from './usage.ts'
export { registerTraeUsageRoute, traeWebUsage, type TraeUsageRouteOptions } from './web-status.ts'
export { TRAE_USAGE_PATH, type TraeWebActivity, type TraeWebCheckin, type TraeWebCredits, type TraeWebUsage } from './status-paths.ts'
export { createTraeShim, type TraeShim } from './shim.ts'
export { UnconfiguredTraeUpstreamClient, type TraeChatResult, type TraeUpstreamClient } from './upstream.ts'

export const name = 'dsh-connect-trae'
export const inject = ['llm']
/**
 * Settings namespace, as a plain lowercase literal. DSH 0.1.2 removed the
 * `settingsNamespace` brand constructor from the npm package (the Desktop
 * host still ships it as a legacy shim), and every consumer of this constant —
 * `registerModelDiscovery`, `registerConfigurableProviders`,
 * `settings.installSection`, the settings test — takes it as a kebab string,
 * so no branding is needed for either host generation.
 */
export const TRAE_SETTINGS_NS = 'trae'

export interface Config {
  authFile?: string
  edition?: 'auto' | 'cn' | 'sg' | 'solo' | 'solo-sg'
  /** Stable local account selector; tokens remain outside settings. */
  accountId?: string
  /** The last-refreshed Trae raw directory; what the plugin card displays. */
  lastCatalog?: TraeModelInfo[]
  /** The user's ordinary-model selection, as model id (= Trae name). */
  enabledModelIds?: string[]
  /** Local DSH context budget per model; a value may only select an advertised window. */
  contextBudgets?: Record<string, number>
  /** Models the user explicitly enabled for image input; text is always enabled. */
  imageModelIds?: string[]
  /** Legacy generated runtime catalog; kept for backwards compatibility. */
  models?: TraeModelInfo[]
}

const modelConfig = z.object({
  id: z.string().required(),
  name: z.string().required(),
  contextWindow: z.number().step(1).min(1),
  maxTokens: z.number().step(1).min(1),
  input: z.array(z.union(['text', 'image'])),
})

export const Config: z<Config> = z.object({
  authFile: z.string().description('Optional Trae storage.json path override'),
  edition: z.union(['auto', 'cn', 'sg', 'solo', 'solo-sg']).default('auto').description('Trae edition hint'),
  accountId: z.string().description('Selected local Trae account id (never a token)'),
  lastCatalog: z.array(modelConfig).description('Last refreshed Trae raw model directory shown by the plugin card') as z<TraeModelInfo[]>,
  enabledModelIds: z.array(z.string()).default([]).description('Trae model ids the user enabled'),
  contextBudgets: z.dict(z.number().step(1).min(1)).default({}).description('Local DSH context budget per Trae model'),
  imageModelIds: z.array(z.string()).default([]).description('Trae model ids the user explicitly enabled for image input'),
  models: z.array(modelConfig).description('Legacy generated Trae model list') as z<TraeModelInfo[]>,
})

export function apply(ctx: Context, config: Config): void {
  const catalog = new TraeCatalog()
  const enabledSet = (value: Config): ReadonlySet<string> => new Set(value.enabledModelIds ?? [])
  const imageSet = (value: Config): ReadonlySet<string> => new Set(value.imageModelIds ?? [])
  // Display keys (lowercased id AND name) of every model known to be callable
  // via `llm_utils_chat`, populated once `discoverModels` merges Remote with
  // `get_detail_param`. A model whose id and name are both absent here is a dead
  // config_name (Remote advertises it, `get_detail_param` has no match, e.g.
  // `Doubao-Seed-Code` / `glm-5.3`) and must never be served — even from a stale
  // saved `lastCatalog` / `models` / `enabledModelIds` that still lists it.
  const callableKeys = new Set<string>()
  // Drop dead rows from a (possibly stale) saved directory. No-op when the wire
  // map has not been resolved yet (startup discovery failed or is in flight),
  // so a transient network failure never hides the whole catalog.
  const dropDeadModels = (rows: readonly TraeModelInfo[]): readonly TraeModelInfo[] => {
    if (callableKeys.size === 0) return rows
    return rows.filter(model =>
      callableKeys.has(model.id.trim().toLowerCase()) || callableKeys.has(model.name.trim().toLowerCase()))
  }
  // Runtime catalog derives from the last-refreshed raw directory plus the
  // user's selection and context budgets. Legacy `models` and pre-budget
  // `lastCatalog` rows are sanitized, so saved `@1m` variants cannot return.
  // Dead config_names are dropped against the live wire map, so a stale save
  // cannot resurrect `Doubao-Seed-Code` / `glm-5.3`. An empty selection serves
  // the whole directory, so a never-configured plugin still exposes models.
  const derive = (value: Config, raw: readonly TraeModelInfo[]): readonly TraeModelInfo[] => {
    const selectedImages = imageSet(value)
    const derived = deriveCatalog(applyImageSelection(sanitizeCatalog(dropDeadModels(raw)), selectedImages), enabledSet(value), value.contextBudgets ?? {})
    return derived.length > 0 ? derived : applyImageSelection(dropDeadModels(FALLBACK_TRAE_MODELS), selectedImages)
  }
  const configuredModels = (value: Config): readonly TraeModelInfo[] =>
    value.lastCatalog?.length ? derive(value, value.lastCatalog)
      : value.models?.length ? derive(value, value.models)
        : applyImageSelection(dropDeadModels(FALLBACK_TRAE_MODELS), imageSet(value))
  // What the plugin card displays: the last-refreshed raw directory, so the
  // user re-reads the current Trae catalog rather than a stale saved snapshot.
  const displayModels = (value: Config): readonly TraeModelInfo[] =>
    value.lastCatalog?.length ? dropDeadModels(sanitizeCatalog(value.lastCatalog))
      : value.models?.length ? dropDeadModels(sanitizeCatalog(value.models))
        : dropDeadModels(FALLBACK_TRAE_MODELS)
  const store = new TraeCredentialStore({
    ...config.authFile === undefined ? {} : { storagePath: config.authFile },
    edition: config.edition ?? 'auto',
    ...config.accountId === undefined ? {} : { accountId: config.accountId },
    refresh: credential => refreshTraeCredential(credential),
  })
  const identity = async () => {
    // Pick the first CN/SOLO candidate whose storage file actually exists,
    // mirroring the credential store's skip-missing semantics. Windows machines
    // often install only SOLO, so pinning the first (cn) candidate and reading a
    // missing file used to throw ENOENT and break every refresh/chat request.
    const candidates = config.authFile === undefined
      ? traeStorageCandidates().filter(item => (item.edition === 'cn' || item.edition === 'solo') && (config.edition === undefined || config.edition === 'auto' || item.edition === config.edition))
      : [{ edition: config.edition === undefined || config.edition === 'auto' ? 'solo' as const : config.edition, path: config.authFile }]
    if (candidates.length === 0) throw new Error('Trae storage was not found')
    return pickTraeStorageIdentity(candidates)
  }
  const solo = new TraeSoloUpstreamClient({
    credential: () => store.resolve(),
    identity,
    baseUrl: 'https://trae-api-cn.mchost.guru',
    log: (message, detail) => ctx.logger.warn(message, detail),
  })
  const remoteCatalog = new TraeSoloRemoteCatalogClient({ credential: () => store.resolve() })
  // Keep the native llm_utils_chat bridge as the only chat route: unlike the
  // polling Remote session API, it preserves Trae's structured tool_calls so
  // DSH can execute local read/write/bash tools and continue the agent loop.
  // A wire resolver maps each display model id to its real llm_utils_chat
  // config_name. It is populated once at startup from get_detail_param and
  // never depends on a user-refreshed or re-saved directory, so Seed-Code and
  // other models whose wire id differs from the display id resolve correctly
  // even on a fresh install.
  const wireById = new Map<string, string>()
  const wireByName = new Map<string, string>()
  const wireResolver = (displayId: string): string | undefined =>
    wireById.get(displayId) ?? wireByName.get(displayId.trim().toLowerCase())
  const upstream = new TraeSoloBridge(solo, catalog, wireResolver)
  // The shim always sees a stable client; the Raw gateway may replace the
  // delegate asynchronously, but it stays disabled until a probe succeeds.
  const delegating = new TraeDelegatingUpstreamClient(upstream)
  const shim = createTraeShim({ catalog, client: delegating, logger: ctx.logger })
  let rawDiagnostic = (): TraeRawDiagnostic => ({ state: 'disabled' })
  void (async () => {
    try {
      const probeModel = 'qwen-3.7-plus'
      const { identity, runtime } = await resolveTraeRawRuntime(store, probeModel)
      const rawClient = new TraeRawChatUpstreamClient({
        credential: () => store.resolve(),
        identity: async () => identity,
        config: { model: runtime.modelName, configName: runtime.configName, passBackReasoning: true, runtime },
        baseUrl: 'https://trae-api-cn.mchost.guru',
      })
      const gateway = createTraeRawGateway({
        raw: rawClient,
        solo: upstream,
        endpoint: 'https://trae-api-cn.mchost.guru/api/ide/v2/llm_raw_chat',
        edition: identity.edition,
        identity: { appVersion: identity.appVersion ?? '', buildVersion: identity.buildVersion ?? '' },
        runtime,
        // Raw Chat stays opt-in and unverified; SOLO remains the only live path.
        enabled: false,
      })
      delegating.replace(gateway.upstream)
      rawDiagnostic = () => gateway.diagnostic()
      ctx.effect(() => () => gateway.invalidate(), 'dsh-connect-trae: Raw capability invalidation')
    } catch (error: unknown) {
      ctx.logger.warn('dsh-connect-trae: Raw gateway unavailable; continuing with native SOLO tool-call channel', error)
    }
  })()

  // Read-only usage/credit summary served to the browser half. Optional on the
  // `webServer` seam; absent in headless runs, the host provider still works.
  //
  // Account selection is strictly the user's choice: the store resolves the
  // explicitly selected `accountId` verbatim, and only falls back to the first
  // discovered account when nothing has been selected yet. The plugin must NOT
  // silently switch to a different account that happens to have general credits
  // — that would bill the wrong account against the user's intent.
  const usageClient = new TraeUsageClient({ credential: () => store.resolve() })
  let current = () => config
  let invalidateAdapter = (): void => {}
  const discoverModels = async (signal?: AbortSignal): Promise<readonly TraeModelInfo[]> => {
    // The Remote /models directory is the model skeleton (display id, name,
    // context, credit, reasoning). get_detail_param only supplies the real
    // llm_utils_chat config_name for models whose display id differs from the
    // wire id (e.g. Seed-Code); it does not define the catalog itself.
    const [remote, wire] = await Promise.all([
      remoteCatalog.fetchModels(signal),
      solo.fetchModels(signal),
    ])
    const merged = mergeTraeModelSources(remote, wire)
    // Record every callable display key (id and name) so stale saved catalogs
    // are filtered against the live wire map and dead config_names cannot be
    // resurrected from an old `lastCatalog` / `models` / `enabledModelIds`.
    callableKeys.clear()
    for (const model of merged) {
      callableKeys.add(model.id.trim().toLowerCase())
      callableKeys.add(model.name.trim().toLowerCase())
    }
    // Populate the startup wire resolver (display id and display name → wire
    // config_name) so the chat bridge resolves the real config_name even when
    // the persisted catalog lacks `wireConfigName` (the settings schema drops
    // unknown fields on save/load).
    wireById.clear()
    wireByName.clear()
    for (const model of merged) {
      if (model.wireConfigName !== undefined) {
        wireById.set(model.id, model.wireConfigName)
        wireByName.set(model.name.trim().toLowerCase(), model.wireConfigName)
      }
    }
    // Persist the merged catalog (including each model's wireConfigName) into
    // the live catalog the chat bridge reads, so requests resolve the real
    // config_name even before the user re-saves the refreshed directory.
    const next = applyImageSelection(merged, imageSet(current()))
    catalog.set(next)
    return merged
  }
  ctx.inject(['webServer'], (webCtx) => registerTraeUsageRoute(webCtx, {
    store,
    client: usageClient,
    displayModels: () => displayModels(current()),
    enabledModelIds: () => current().enabledModelIds ?? [],
    discoverModels,
    rawDiagnostic: () => rawDiagnostic(),
  }))

  const sectionHooks: SettingsSectionHooks<Config> = {
    setSource(source) { current = source },
    onChange() {
      const next = current()
      store.setSource(next.authFile, next.edition ?? 'auto', next.accountId)
      catalog.set(configuredModels(next))
      invalidateAdapter()
    },
  }
  // DSH 0.1.2 replaced the free `installSettingsSection` helper with the
  // `settings` service's `installSection` method. The Desktop host keeps the
  // old helper as a legacy shim, but npm installs of 0.1.2 do not — and a
  // named import of a missing export fails at ESM link time, so the plugin
  // reads it defensively off the module namespace. Prefer the helper when it
  // exists (0.1.1 hosts and shimmed 0.1.2 hosts) and fall back to the service
  // method everywhere else, so one build serves both host generations.
  const legacyInstallSettingsSection = (dshSettings as {
    installSettingsSection?: (ctx: Context, ns: string, schema: z<Config>, entry: Config, hooks: SettingsSectionHooks<Config>) => void
  }).installSettingsSection
  if (typeof legacyInstallSettingsSection === 'function') {
    legacyInstallSettingsSection(ctx, TRAE_SETTINGS_NS, Config, config, sectionHooks)
  } else {
    ctx.inject(['settings'], settingsCtx => {
      settingsCtx.settings.installSection(ctx, TRAE_SETTINGS_NS, Config, config, sectionHooks)
    })
  }

  let stopped = false
  ctx.effect(() => () => {
    stopped = true
    void shim.close()
  })

  void shim.ready.then(async () => {
    if (stopped) return
    // Resolve the wire-id map once at startup before serving requests, so the
    // chat bridge can translate display ids to real config_names without the
    // user ever opening the model card or re-saving the directory.
    try {
      await discoverModels()
    } catch (error: unknown) {
      ctx.logger.warn('dsh-connect-trae: wire-id resolution failed at startup; falling back to display ids', error)
    }
    catalog.set(configuredModels(current()))
    const trae = createTraeAdapter({
      shim,
      catalog,
      resolveAttachments: () => ctx.get('attachments'),
    })
    invalidateAdapter = () => { trae.invalidate() }
    let releaseAdapter: (() => void) | undefined
    let releaseDirectory: (() => void) | undefined
    try {
      releaseAdapter = ctx.llm.registerAdapter([TRAE_PROVIDER], trae.adapter)
      ctx.llm.registerModelDiscovery(TRAE_SETTINGS_NS, async (request, signal) => {
        if (request.provider !== TRAE_PROVIDER) return []
        // Discovery must advertise the same image capability as the live
        // adapter catalog. The upstream flag is deliberately ignored; only the
        // user's explicit `imageModelIds` selection is authoritative.
        //
        // DSH 0.1.2 moved discovery cancellation from `request.signal` onto
        // the callback's second argument; 0.1.1 hosts still pass it on the
        // request object, so read both.
        const cancellation = signal ?? (request as { signal?: AbortSignal }).signal
        const next = applyImageSelection(
          await discoverModels(cancellation),
          imageSet(current()),
        )
        return next.map(model => ({
          id: model.id,
          name: model.name,
          ...model.contextWindow === undefined ? {} : { contextWindow: model.contextWindow },
          ...model.maxTokens === undefined ? {} : { maxTokens: model.maxTokens },
          // Current dsh-llm discovery types do not yet declare this field, but
          // model-management consumers already understand it. Keep the value
          // aligned with the adapter catalog; DSH core may discard it today.
          inputModalities: traeInputModalities(model),
        }))
      })
      releaseDirectory = ctx.llm.registerConfigurableProviders([{
        provider: TRAE_PROVIDER,
        displayName: 'Trae',
        settingsNs: TRAE_SETTINGS_NS,
        settingsPath: [],
        declared: false,
      }])
    } finally {
      if (releaseAdapter === undefined || releaseDirectory === undefined) {
        releaseAdapter?.()
        releaseDirectory?.()
      }
    }
    try {
      ctx.effect(() => () => {
        releaseAdapter?.()
        releaseDirectory?.()
      })
    } catch {
      releaseAdapter?.()
      releaseDirectory?.()
    }
  }).catch((error: unknown) => {
    ctx.logger.error('dsh-connect-trae: loopback shim failed; provider not registered', error)
  })
}
