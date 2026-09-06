import { describe, expect, it } from 'vitest'
import type { TraeDiscoveredModel } from '../src/model-metadata.ts'
import {
  applyContextBudgets,
  applyImageSelection,
  deriveCatalog,
  discoveredCatalog,
  FALLBACK_TRAE_MODELS,
  mergeTraeModelSources,
  sanitizeCatalog,
  TraeCatalog,
  traeInputModalities,
} from '../src/catalog.ts'

const RAW = discoveredCatalog([{
  id: 'qwen3.8-max', name: 'Qwen3.8-Max', multimodal: true,
  contextWindow: 200_000, maxContextWindow: 1_000_000, creditMultiplier: 1.5,
  reasoningSupported: true,
  reasoning: { supported: ['low', 'high', 'xhigh'], defaultEffort: 'high' },
}, {
  id: 'deepseek-v4-pro', name: 'DeepSeek-V4-Pro', multimodal: false,
  contextWindow: 200_000, reasoningSupported: false,
}])

describe('Trae catalog', () => {
  it('starts with identity-only fallback entries that default to text-only', () => {
    const catalog = new TraeCatalog()
    expect(catalog.current()).toEqual(FALLBACK_TRAE_MODELS)
    expect(catalog.current().some(model => model.id === 'DeepSeek-V4-Flash')).toBe(true)
    expect(catalog.current().every(model => model.contextWindow === undefined)).toBe(true)
    expect(traeInputModalities(FALLBACK_TRAE_MODELS.find(model => model.id === 'glm-5.2')!)).toEqual(['text'])
    expect(traeInputModalities(FALLBACK_TRAE_MODELS.find(model => model.id === 'kimi-k2.6')!)).toEqual(['text'])
    expect(traeInputModalities(FALLBACK_TRAE_MODELS.find(model => model.id === 'DeepSeek-V4-Pro')!)).toEqual(['text'])
  })

  it('ignores uncertain upstream multimodal flags and keeps one text-only entry per model', () => {
    expect(RAW).toEqual([
      expect.objectContaining({
        id: 'qwen3.8-max', contextWindow: 200_000, maxContextWindow: 1_000_000,
        creditMultiplier: 1.5, input: ['text'],
      }),
      expect.objectContaining({ id: 'deepseek-v4-pro', contextWindow: 200_000, input: ['text'] }),
    ])
    expect(RAW.some(model => model.id.includes('@1m'))).toBe(false)
  })

  it('uses only explicit image opt-ins and overwrites stale saved modalities', () => {
    const stale = RAW.map(model => ({ ...model, input: ['text', 'image'] as ('text' | 'image')[] }))
    expect(applyImageSelection(stale, new Set(['qwen3.8-max']))).toEqual([
      expect.objectContaining({ id: 'qwen3.8-max', input: ['text', 'image'] }),
      expect.objectContaining({ id: 'deepseek-v4-pro', input: ['text'] }),
    ])
    expect(applyImageSelection(stale, new Set()).every(model => model.input?.join(',') === 'text')).toBe(true)
  })

  it('serves the whole directory when nothing is enabled yet', () => {
    expect(deriveCatalog(RAW, new Set()).map(model => model.id)).toEqual([
      'qwen3.8-max',
      'deepseek-v4-pro',
    ])
  })

  it('applies the advertised Max budget without creating a variant model', () => {
    const derived = deriveCatalog(
      RAW,
      new Set(['qwen3.8-max']),
      { 'qwen3.8-max': 1_000_000 },
    )
    expect(derived).toEqual([
      expect.objectContaining({
        id: 'qwen3.8-max', contextWindow: 1_000_000,
        maxContextWindow: 1_000_000, input: ['text'],
      }),
    ])
    expect(derived.some(model => model.id.includes('@1m'))).toBe(false)
    expect(applyContextBudgets(RAW, { 'qwen3.8-max': 999_999 })[0]?.contextWindow).toBe(200_000)
  })

  it('drops legacy variant rows and rejects replacing the live catalog with an empty list', () => {
    const legacy = [
      RAW[0]!,
      { ...RAW[0]!, id: 'qwen3.8-max@1m', contextWindow: 1_000_000, baseModelId: 'qwen3.8-max', maxContext: true },
    ]
    expect(sanitizeCatalog(legacy).map(model => model.id)).toEqual(['qwen3.8-max'])
    expect(() => new TraeCatalog().set([])).toThrow(/cannot be empty/)
  })
})

describe('mergeTraeModelSources', () => {
  it('keeps the remote directory id as the model id and attaches the wire config_name', () => {
    const remote: TraeDiscoveredModel[] = [
      { id: 'Doubao-Seed-Code', name: 'Seed-Code', multimodal: true, contextWindow: 128_000, maxContextWindow: 256_000, creditMultiplier: 1.5, reasoningSupported: true, reasoning: { supported: ['low', 'high', 'xhigh'], defaultEffort: 'high' } },
      { id: 'glm-5.2', name: 'GLM-5.2', multimodal: false, contextWindow: 168_000, reasoningSupported: false },
    ]
    const wire = [
      { id: 'Doubao_1_6', name: 'Seed-Code' },
      { id: 'glm-5.2', name: 'GLM-5.2' },
    ]
    const merged = mergeTraeModelSources(remote, wire)
    expect(merged.map(model => model.id)).toEqual(['Doubao-Seed-Code', 'glm-5.2'])
    expect(merged[0]).toMatchObject({
      id: 'Doubao-Seed-Code',
      name: 'Seed-Code',
      contextWindow: 128_000,
      maxContextWindow: 256_000,
      creditMultiplier: 1.5,
      input: ['text'],
      wireConfigName: 'Doubao_1_6',
    })
    // Reasoning comes from the remote skeleton, mapped to Trae wire effort strings.
    expect(merged[0]?.reasoningEfforts).toEqual({ low: 'light', high: 'high', xhigh: 'extra_high' })
    // A remote model whose wire id equals its own id needs no wireConfigName.
    expect(merged[1]).toMatchObject({ id: 'glm-5.2', name: 'GLM-5.2', input: ['text'] })
    expect(merged[1]?.wireConfigName).toBeUndefined()
  })

  it('joins by config_name id first, then display name case-insensitively, and drops wire-only rows', () => {
    const remote: TraeDiscoveredModel[] = [
      // Exact id match: id is already the wire config_name.
      { id: 'glm-5.2', name: 'GLM-5.2', multimodal: false, reasoningSupported: false },
      // Display-name match with a differing wire id → wireConfigName attached.
      { id: 'remote-doubao', name: 'seed-code', multimodal: true, reasoningSupported: false, creditMultiplier: 2 },
    ]
    const wire = [
      { id: 'glm-5.2', name: 'GLM-5.2' },
      { id: 'wire-doubao', name: 'SEED-CODE' },
      { id: 'wire-orphan', name: 'No Remote Match' },
    ]
    const merged = mergeTraeModelSources(remote, wire)
    expect(merged.map(model => model.id)).toEqual(['glm-5.2', 'remote-doubao'])
    expect(merged[1]?.wireConfigName).toBe('wire-doubao')
    expect(merged[1]?.creditMultiplier).toBe(2)
    // The wire-only orphan is dropped (no remote skeleton to expose).
    expect(merged.some(model => model.id === 'wire-orphan')).toBe(false)
  })

  it('drops remote models that map to no wire config_name (uncallable → would 4001)', () => {
    // Doubao-Seed-Code and glm-5.3 are advertised by the Remote directory but
    // are NOT current `config_name`s in get_detail_param; sending them makes
    // every request fail with 4001 "param is invalid". They must not ship.
    const remote: TraeDiscoveredModel[] = [
      { id: 'Doubao-Seed-Code', name: 'Seed-Code', multimodal: true, reasoningSupported: true },
      { id: 'glm-5.3', name: 'GLM-5.3', multimodal: false, reasoningSupported: false },
      { id: 'glm-5.2', name: 'GLM-5.2', multimodal: false, reasoningSupported: false },
    ]
    const wire = [
      { id: 'glm-5.2', name: 'GLM-5.2' },
      { id: 'Doubao-Seed-2.0-Code', name: 'Doubao-Seed-2.1-Turbo' },
    ]
    const merged = mergeTraeModelSources(remote, wire)
    expect(merged.map(model => model.id)).toEqual(['glm-5.2'])
  })
})
