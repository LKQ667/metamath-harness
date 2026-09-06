import { describe, expect, it } from 'vitest'
import { parseObservedModelConfig } from '../src/model-config.ts'

describe('observed Trae model config', () => {
  it('parses preset model values and preserves None as absence', () => {
    const line = 'model_info: CustomModel { provider: Some(""), is_preset: true, config_name: "glm-5.2", config_source: Trae, model_name: "glm-5.2", raw_chat_function: None, prompt_set: None, ab_versions: None } trace_id="redacted"'
    expect(parseObservedModelConfig(line)).toEqual({ configName: 'glm-5.2', modelName: 'glm-5.2' })
  })

  it('reads optional values only when Trae reports Some', () => {
    const line = 'model_info: CustomModel { config_name: "m", model_name: "upstream", raw_chat_function: Some("inline_chat"), prompt_set: Some("set-a"), ab_versions: Some("ab-a") } trace_id="redacted"'
    expect(parseObservedModelConfig(line)).toEqual({ configName: 'm', modelName: 'upstream', rawChatFunction: 'inline_chat', promptSet: 'set-a', abVersion: 'ab-a' })
  })

  it('rejects unrelated or incomplete lines', () => {
    expect(parseObservedModelConfig('other')).toBeUndefined()
    expect(parseObservedModelConfig('model_info: CustomModel { config_name: "m" }')).toBeUndefined()
  })
})
