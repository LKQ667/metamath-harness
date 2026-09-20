/** DSH configuration schema and region-scoped model catalog migration rules. */

import z from '@deepseek-ai/schemastery'
import { defaultModels, type QoderCatalogModel } from '../qoder/catalog.ts'
import type { QoderRegion } from '../qoder/region.ts'
import { defaultResponseHeaderTimeoutMs, defaultStreamIdleTimeoutMs } from '../qoder/transport/index.ts'

export interface QoderModelsByRegion {
  global?: QoderCatalogModel[]
  china?: QoderCatalogModel[]
}

export type QoderWebSearchMode = 'auto' | 'always' | 'disabled'

export interface Config {
  region?: QoderRegion
  modelsByRegion?: QoderModelsByRegion
  /** @deprecated Migrated to modelsByRegion for the selected region. */
  models?: QoderCatalogModel[]
  streamIdleTimeoutMs?: number
  responseHeaderTimeoutMs?: number
  preserveThinking?: boolean
  webSearchMode?: QoderWebSearchMode
}

const catalogModel: z<QoderCatalogModel> = z.object({
  id: z.string().required(),
  name: z.string().required(),
  description: z.string(),
  contextWindow: z.number().step(1).min(1),
  maxContextWindow: z.number().step(1).min(1),
  maxTokens: z.number().step(1).min(1),
  source: z.string(),
  isReasoning: z.boolean(),
  supportsEffort: z.boolean(),
  reasoningEfforts: z.array(z.object({
    id: z.string().required(),
    name: z.string().required(),
    description: z.string(),
  })),
  defaultReasoningEffort: z.string(),
  priceFactor: z.number().min(0),
  supportsImages: z.boolean(),
  contextOptions: z.dict(z.object({
    tokenCount: z.number().step(1).min(1),
    isDefault: z.boolean(),
  })),
})

const modelsByRegionSchema = z.dict(z.array(catalogModel)) as z<QoderModelsByRegion>

export const Config: z<Config> = z.object({
  region: z.union(['global', 'china'] as const).default('global'),
  modelsByRegion: modelsByRegionSchema.default({}),
  models: z.array(catalogModel),
  streamIdleTimeoutMs: z.number().step(1).min(1).default(defaultStreamIdleTimeoutMs),
  responseHeaderTimeoutMs: z.number().step(1).min(1).default(defaultResponseHeaderTimeoutMs),
  preserveThinking: z.boolean().default(true),
  webSearchMode: z.union(['auto', 'always', 'disabled'] as const).default('auto'),
})

export function resolveModels(models: readonly QoderCatalogModel[] | undefined): QoderCatalogModel[] {
  const resolved = models ?? defaultModels
  if (resolved.length === 0) throw new Error('provider-qoder: at least one model is required')
  const seen = new Set<string>()
  return resolved.map((model) => {
    if (!model.id || !model.name) throw new Error('provider-qoder: model id and name must be non-empty')
    if (seen.has(model.id)) throw new Error(`provider-qoder: duplicate model id "${model.id}"`)
    seen.add(model.id)
    return { ...model }
  })
}

export function modelsFor(
  config: Config,
  region: QoderRegion,
  legacyModelsRegion: QoderRegion = config.region ?? 'global',
): QoderCatalogModel[] {
  const scoped = config.modelsByRegion?.[region]
  if (scoped !== undefined) return resolveModels(scoped)
  if (legacyModelsRegion === region && config.models !== undefined && config.models.length > 0) {
    return resolveModels(config.models)
  }
  return resolveModels(defaultModels)
}
