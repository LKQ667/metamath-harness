import type { TraeDiscoveredModel, TraeDiscoveredReasoning } from './model-metadata.ts'
import type { TraeReasoningEffort } from './reasoning.ts'
import type { TraeReasoningCapability } from './reasoning.ts'

export type TraeInputModality = 'text' | 'image'

/**
 * One model the adapter exposes. `contextWindow` is the effective DSH context
 * after the user's budget; `maxContextWindow` is the native Max window Trae
 * advertises (capability display only — never a second model entry).
 */
export interface TraeModelInfo {
  id: string
  name: string
  contextWindow?: number
  maxTokens?: number
  input?: TraeInputModality[]
  creditMultiplier?: number
  reasoningSupported?: boolean
  reasoning?: TraeDiscoveredReasoning
  reasoningEfforts?: Partial<Record<TraeReasoningEffort, string | null>>
  maxContextWindow?: number
  /** The `config_name` `llm_utils_chat` accepts; absent means `id` is already the wire id. */
  wireConfigName?: string
}

/** Bootstrap catalog: identity only where current Trae metadata has not been fetched yet. */
export const FALLBACK_TRAE_MODELS: readonly TraeModelInfo[] = [
  { id: 'auto', name: 'Auto' },
  { id: 'DeepSeek-V4-Flash', name: 'DeepSeek-V4-Flash' },
  { id: 'DeepSeek-V4-Pro', name: 'DeepSeek-V4-Pro' },
  { id: 'glm-5.2', name: 'GLM-5.2' },
  { id: 'kimi-k2.6', name: 'Kimi-K2.6' },
]

/** Exact DSH modalities for one catalog entry; absent metadata is text-only. */
export function traeInputModalities(model: Pick<TraeModelInfo, 'input'>): TraeInputModality[] {
  return [...(model.input ?? ['text'])]
}

/** Apply the user's explicit image opt-ins; upstream and saved row hints are ignored. */
export function applyImageSelection(
  models: readonly TraeModelInfo[],
  selected: ReadonlySet<string>,
): TraeModelInfo[] {
  return models.map(model => ({ ...model, input: selected.has(model.id) ? ['text', 'image'] : ['text'] }))
}

/** One row from `get_detail_param`: the authoritative llm_utils_chat wire id + display name. */
export interface TraeWireModel {
  id: string
  name: string
  contextWindow?: number
  maxTokens?: number
  reasoning?: TraeReasoningCapability
}

/** Normalise a display name for cross-source joining. */
function displayKey(name: string): string {
  return name.trim().toLowerCase()
}

/**
 * Merge the two Trae model sources into one authoritative catalog.
 *
 * `remote` (the solo.trae.cn `/models` directory) is the authoritative model
 * skeleton: it supplies the display id, display name, context windows, credit
 * multiplier, reasoning and multimodal flags. `wire` (from `get_detail_param`)
 * supplies the real `llm_utils_chat` `config_name` — the only id the chat
 * endpoint actually accepts. A remote row is only callable when it maps to a
 * wire `config_name`, so a remote row with no wire match is DROPPED (it would
 * otherwise be sent as an invalid `config_name` and rejected with 4001
 * "param is invalid"). Verified 2026-08-30: the Remote directory advertises
 * `Doubao-Seed-Code` and `glm-5.3`, neither of which is a current `config_name`;
 * both fail every request, so they must not be exposed.
 *
 * Joining is two-tier, in priority order:
 *  1. `wire.id` (the `config_name`) equals the remote id — the model's display
 *     id is already its wire id (the common case: glm-5.2, DeepSeek-V4-Flash,
 *     kimi-k3, …).
 *  2. `wire.name` (the `display_name`) equals the remote display name — for
 *     models whose display id differs from the wire id across Trae versions.
 * When the matched wire `config_name` differs from the remote id it is recorded
 * as `wireConfigName`; otherwise it is left undefined (id is already the wire id).
 */
export function mergeTraeModelSources(
  remote: readonly TraeDiscoveredModel[],
  wire: readonly TraeWireModel[],
): TraeModelInfo[] {
  const wireByName = new Map<string, TraeWireModel>()
  const wireById = new Map<string, TraeWireModel>()
  for (const model of wire) {
    wireByName.set(displayKey(model.name), model)
    wireById.set(displayKey(model.id), model)
  }
  const result: TraeModelInfo[] = []
  for (const model of remote) {
    const wireModel = wireById.get(displayKey(model.id)) ?? wireByName.get(displayKey(model.name))
    // No config_name maps to this display id → uncallable via llm_utils_chat.
    // Drop it rather than advertise a model that always fails with 4001.
    if (wireModel === undefined) continue
    result.push({
      id: model.id,
      name: model.name,
      ...model.contextWindow === undefined ? {} : { contextWindow: model.contextWindow },
      ...model.maxContextWindow === undefined ? {} : { maxContextWindow: model.maxContextWindow },
      ...model.creditMultiplier === undefined ? {} : { creditMultiplier: model.creditMultiplier },
      input: ['text'],
      reasoningSupported: model.reasoningSupported,
      ...model.reasoning === undefined ? {} : {
        reasoning: model.reasoning,
        reasoningEfforts: Object.fromEntries(model.reasoning.supported.map(effort => [effort, effort === 'low' ? 'light' : effort === 'xhigh' ? 'extra_high' : 'high'])) as Partial<Record<TraeReasoningEffort, string>>,
      },
      ...wireModel.id !== '' && wireModel.id !== model.id ? { wireConfigName: wireModel.id } : {},
    })
  }
  return result
}

/** Local DSH context budget per model; a value may only select an advertised window. */
export type TraeContextBudget = number

/**
 * Apply the saved local budget. Trae advertises two windows per model (dev and
 * Max), so the budget may only switch a model to its own advertised Max value —
 * never to a fabricated number. Everything else keeps the dev window.
 */
export function applyContextBudgets(
  catalog: readonly TraeModelInfo[],
  budgets: Readonly<Record<string, TraeContextBudget | undefined>> = {},
): TraeModelInfo[] {
  return catalog.map(model => ({
    ...model,
    ...(model.maxContextWindow !== undefined && budgets[model.id] === model.maxContextWindow
      ? { contextWindow: model.maxContextWindow }
      : {}),
  }))
}

/** Convert Trae metadata into text-only model rows; image support is user-owned configuration. */
export function discoveredCatalog(models: readonly TraeDiscoveredModel[]): TraeModelInfo[] {
  const result: TraeModelInfo[] = []
  for (const model of models) {
    result.push({
      id: model.id,
      name: model.name,
      ...model.contextWindow === undefined ? {} : { contextWindow: model.contextWindow },
      ...model.maxContextWindow === undefined ? {} : { maxContextWindow: model.maxContextWindow },
      input: ['text'],
      ...model.creditMultiplier === undefined ? {} : { creditMultiplier: model.creditMultiplier },
      reasoningSupported: model.reasoningSupported,
      ...model.reasoning === undefined ? {} : {
        reasoning: model.reasoning,
        reasoningEfforts: Object.fromEntries(model.reasoning.supported.map(effort => [effort, effort === 'low' ? 'light' : effort === 'xhigh' ? 'extra_high' : 'high'])) as Partial<Record<TraeReasoningEffort, string>>,
      },
    })
  }
  return result
}

/**
 * Drop rows saved by older releases that generated `@1m` variant models, so a
 * stale configuration cannot resurrect a variant the runtime no longer builds.
 */
export function sanitizeCatalog(catalog: readonly TraeModelInfo[]): TraeModelInfo[] {
  return catalog.filter(model => {
    if (model.id.endsWith('@1m')) return false
    const legacy = model as Partial<{ baseModelId: unknown; maxContext: unknown }>
    return legacy.baseModelId === undefined && legacy.maxContext !== true
  })
}

/**
 * Derive the runtime catalog from the last refreshed Trae directory plus the
 * user's explicit selection and context budgets. An empty selection falls back
 * to the whole directory: a plugin that has never been configured must still
 * serve models rather than nothing. This is the single source of truth for
 * what DSH actually exposes, so saving only the selection and budgets is
 * enough to rebuild it after a restart.
 */
export function deriveCatalog(
  catalog: readonly TraeModelInfo[],
  enabled: ReadonlySet<string>,
  budgets: Readonly<Record<string, TraeContextBudget | undefined>> = {},
): TraeModelInfo[] {
  const selected = enabled.size === 0 ? catalog : catalog.filter(model => enabled.has(model.id))
  return applyContextBudgets(selected, budgets)
}

export class TraeCatalog {
  private models: readonly TraeModelInfo[] = FALLBACK_TRAE_MODELS

  current(): readonly TraeModelInfo[] {
    return this.models
  }

  set(models: readonly TraeModelInfo[]): void {
    if (models.length === 0) throw new Error('trae model catalog cannot be empty')
    this.models = models.map(model => ({ ...model, ...model.input === undefined ? {} : { input: [...model.input] } }))
  }
}
