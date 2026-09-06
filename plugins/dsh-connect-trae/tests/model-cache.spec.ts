import { describe, expect, it } from 'vitest'
import { parseTraeCachedModel } from '../src/model-cache.ts'

describe('Trae cached model config', () => {
  it('keeps only safe prompt/model fields and parses custom_config', () => {
    expect(parseTraeCachedModel({
      name: 'qwen-3.7-plus', multimodal: true, model_type: 'reasoning_model',
      custom_config: '{"native_function_call":true,"use_v2_process":true}',
      prompt_max_tokens: 168000, max_tokens: 32000, max_turn: 500,
      ak: 'must-not-leak', base_url: 'must-not-leak', icon: { dark: 'must-not-leak' },
    })).toEqual({
      name: 'qwen-3.7-plus', multimodal: true, modelType: 'reasoning_model',
      customConfig: { native_function_call: true, use_v2_process: true },
      promptMaxTokens: 168000, maxTokens: 32000, maxTurn: 500,
    })
  })

  it('does not invent invalid or missing values', () => {
    expect(parseTraeCachedModel({ name: 'm', custom_config: '{bad', max_tokens: 0 })).toEqual({ name: 'm' })
    expect(parseTraeCachedModel({})).toBeUndefined()
  })
})
