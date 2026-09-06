import type { TraeCachedModelConfig } from './model-cache.ts'
import type { TraeRawChatBehaviorConfig } from './model-extra-config.ts'

export interface TraeRawChatRuntimeConfig {
  configName: string
  modelName: string
  promptMaxTokens?: number
  maxTokens?: number
  maxTurn?: number
  multimodal?: boolean
  nativeFunctionCall?: boolean
  passBackReasoning?: boolean
  useV2Process?: boolean
  maxModeEnabled?: boolean
  maxToolcallChars?: number
  streamThrottleEnabled?: boolean
  customConfig?: Record<string, unknown>
}

/** Merge safe current-cache facts with observed behavior flags; no network credentials enter this object. */
export function traeRawChatExtraInfo(config: TraeRawChatRuntimeConfig): Record<string, unknown> {
  return {
    ...config.nativeFunctionCall === undefined ? {} : { native_function_call: config.nativeFunctionCall },
    ...config.useV2Process === undefined ? {} : { use_v2_process: config.useV2Process },
    ...config.maxModeEnabled === undefined ? {} : { v2_max_mode_enabled: config.maxModeEnabled },
    ...config.maxToolcallChars === undefined ? {} : { v3_max_toolcall_chars: config.maxToolcallChars },
    ...config.streamThrottleEnabled === undefined ? {} : { v3_stream_throttle_enabled: config.streamThrottleEnabled },
  }
}

export function buildTraeRawChatRuntimeConfig(
  modelName: string,
  cached: TraeCachedModelConfig | undefined,
  behavior: TraeRawChatBehaviorConfig = {},
): TraeRawChatRuntimeConfig {
  return {
    configName: modelName,
    modelName,
    ...cached?.promptMaxTokens === undefined ? {} : { promptMaxTokens: cached.promptMaxTokens },
    ...cached?.maxTokens === undefined ? {} : { maxTokens: cached.maxTokens },
    ...cached?.maxTurn === undefined ? {} : { maxTurn: cached.maxTurn },
    ...cached?.multimodal === undefined ? {} : { multimodal: cached.multimodal },
    ...cached?.customConfig === undefined ? {} : { customConfig: structuredClone(cached.customConfig) },
    ...behavior.nativeFunctionCall === undefined ? {} : { nativeFunctionCall: behavior.nativeFunctionCall },
    ...behavior.passBackReasoning === undefined ? {} : { passBackReasoning: behavior.passBackReasoning },
    ...behavior.useV2Process === undefined ? {} : { useV2Process: behavior.useV2Process },
    ...behavior.maxModeEnabled === undefined ? {} : { maxModeEnabled: behavior.maxModeEnabled },
    ...behavior.maxToolcallChars === undefined ? {} : { maxToolcallChars: behavior.maxToolcallChars },
    ...behavior.streamThrottleEnabled === undefined ? {} : { streamThrottleEnabled: behavior.streamThrottleEnabled },
  }
}
