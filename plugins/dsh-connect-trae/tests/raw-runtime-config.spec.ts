import { describe, expect, it } from 'vitest'
import { buildTraeRawChatRuntimeConfig, traeRawChatExtraInfo } from '../src/raw-runtime-config.ts'

describe('Trae Raw Chat runtime config', () => {
  it('merges safe cached model facts and observed behavior switches', () => {
    expect(buildTraeRawChatRuntimeConfig('qwen-3.7-plus', {
      name: 'qwen-3.7-plus', promptMaxTokens: 168000, maxTokens: 32000, maxTurn: 500,
      multimodal: true, customConfig: { native_function_call: true, use_v2_process: true },
    }, {
      passBackReasoning: true, nativeFunctionCall: true, useV2Process: true,
      maxModeEnabled: false, maxToolcallChars: 30000, streamThrottleEnabled: true,
    })).toEqual({
      configName: 'qwen-3.7-plus', modelName: 'qwen-3.7-plus', promptMaxTokens: 168000,
      maxTokens: 32000, maxTurn: 500, multimodal: true,
      customConfig: { native_function_call: true, use_v2_process: true },
      passBackReasoning: true, nativeFunctionCall: true, useV2Process: true,
      maxModeEnabled: false, maxToolcallChars: 30000, streamThrottleEnabled: true,
    })
  })

  it('projects only verified behavior switches into Raw Chat extra_info', () => {
    const runtime = buildTraeRawChatRuntimeConfig('m', undefined, {
      nativeFunctionCall: true, useV2Process: true, maxModeEnabled: true,
      maxToolcallChars: 30000, streamThrottleEnabled: true, passBackReasoning: true,
    })
    expect(traeRawChatExtraInfo(runtime)).toEqual({
      native_function_call: true, use_v2_process: true, v2_max_mode_enabled: true,
      v3_max_toolcall_chars: 30000, v3_stream_throttle_enabled: true,
    })
  })

  it('does not invent unavailable model behavior', () => {
    expect(buildTraeRawChatRuntimeConfig('m', undefined)).toEqual({ configName: 'm', modelName: 'm' })
  })
})
