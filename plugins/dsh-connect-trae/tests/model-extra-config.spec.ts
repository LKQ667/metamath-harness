import { describe, expect, it } from 'vitest'
import { parseTraeModelExtraConfigLogLine, parseTraeRawChatBehaviorConfig } from '../src/model-extra-config.ts'

describe('Trae model extra config', () => {
  it('keeps only observed Raw Chat behavior switches', () => {
    expect(parseTraeRawChatBehaviorConfig({
      pass_back_reasoning: true,
      native_function_call: true,
      use_v2_process: true,
      v2_max_mode_enabled: true,
      v3_max_toolcall_chars: 30000,
      v3_stream_throttle_enabled: true,
      unrelated: 'ignored',
    })).toEqual({
      passBackReasoning: true,
      nativeFunctionCall: true,
      useV2Process: true,
      maxModeEnabled: true,
      maxToolcallChars: 30000,
      streamThrottleEnabled: true,
    })
  })

  it('extracts a native log raw JSON suffix without exposing the rest of the line', () => {
    expect(parseTraeModelExtraConfigLogLine('ERROR failed, raw: {"pass_back_reasoning":true,"native_function_call":true}')).toEqual({
      passBackReasoning: true, nativeFunctionCall: true,
    })
    expect(parseTraeModelExtraConfigLogLine('no marker')).toBeUndefined()
  })
})
