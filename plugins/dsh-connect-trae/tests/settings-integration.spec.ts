import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import LlmRuntime from '@deepseek-ai/dsh-llm'
import SettingsProvider from '@deepseek-ai/dsh-settings'
import type { SettingsNamespace } from '@deepseek-ai/dsh-settings'
import * as Trae from '../src/index.ts'

class MemorySettings extends SettingsProvider {
  readonly writable = true
  private storedDocument: Record<string, unknown> = {}
  protected load(): Promise<Record<string, unknown>> { return Promise.resolve(structuredClone(this.storedDocument)) }
  protected persist(ns: SettingsNamespace, section: Record<string, unknown>): Promise<void> {
    this.storedDocument[ns] = structuredClone(section)
    return Promise.resolve()
  }
}

let context: Context | undefined
afterEach(async () => { await context?.fiber.dispose(); context = undefined })

describe('Trae provider registration', () => {
  it('registers provider, settings, and fallback models after shim startup', async () => {
    const ctx = new Context()
    context = ctx
    await ctx.plugin(LlmRuntime)
    await ctx.plugin(MemorySettings)
    await ctx.plugin(Trae, { edition: 'auto' })
    await expect.poll(() => ctx.llm.listProviders().map(provider => provider.id)).toContain('trae')
    expect(ctx.llm.listConfigurableProviders()).toContainEqual({
      provider: 'trae', displayName: 'Trae', settingsNs: 'trae', settingsPath: [], declared: false,
    })
    expect(ctx.settings.describe().some(entry => entry.ns === Trae.TRAE_SETTINGS_NS)).toBe(true)
    const models = await ctx.llm.listModels('trae')
    expect(models.map(model => model.id)).toContain('DeepSeek-V4-Flash')
    expect(models.map(model => model.id)).toContain('DeepSeek-V4-Pro')
    expect(models.find(model => model.id === 'glm-5.2')?.inputModalities).toEqual(['text'])
    expect(models.find(model => model.id === 'kimi-k2.6')?.inputModalities).toEqual(['text'])
    expect(models.find(model => model.id === 'DeepSeek-V4-Pro')?.inputModalities).toEqual(['text'])
  })

  it('applies the explicit image opt-in to the live adapter catalog', async () => {
    const ctx = new Context()
    context = ctx
    await ctx.plugin(LlmRuntime)
    await ctx.plugin(MemorySettings)
    await ctx.plugin(Trae, { edition: 'auto' })
    await expect.poll(() => ctx.llm.listProviders().map(provider => provider.id)).toContain('trae')

    await ctx.settings.update(Trae.TRAE_SETTINGS_NS, { imageModelIds: ['DeepSeek-V4-Pro'] })

    const models = await ctx.llm.listModels('trae')
    expect(models.find(model => model.id === 'DeepSeek-V4-Pro')?.inputModalities).toEqual(['text', 'image'])
    expect(models.find(model => model.id === 'DeepSeek-V4-Flash')?.inputModalities).toEqual(['text'])
  })
})
