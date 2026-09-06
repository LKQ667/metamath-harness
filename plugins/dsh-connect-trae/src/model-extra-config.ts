export interface TraeRawChatBehaviorConfig {
  passBackReasoning?: boolean
  nativeFunctionCall?: boolean
  useV2Process?: boolean
  maxModeEnabled?: boolean
  maxToolcallChars?: number
  streamThrottleEnabled?: boolean
}

function positive(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}

/** Parse only Raw Chat behavior switches observed in Trae's model_extra_config. */
export function parseTraeRawChatBehaviorConfig(value: unknown): TraeRawChatBehaviorConfig {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return {}
  const raw = value as Record<string, unknown>
  const maxToolcallChars = positive(raw['v3_max_toolcall_chars'])
  return {
    ...typeof raw['pass_back_reasoning'] === 'boolean' ? { passBackReasoning: raw['pass_back_reasoning'] } : {},
    ...typeof raw['native_function_call'] === 'boolean' ? { nativeFunctionCall: raw['native_function_call'] } : {},
    ...typeof raw['use_v2_process'] === 'boolean' ? { useV2Process: raw['use_v2_process'] } : {},
    ...typeof raw['v2_max_mode_enabled'] === 'boolean' ? { maxModeEnabled: raw['v2_max_mode_enabled'] } : {},
    ...maxToolcallChars === undefined ? {} : { maxToolcallChars },
    ...typeof raw['v3_stream_throttle_enabled'] === 'boolean' ? { streamThrottleEnabled: raw['v3_stream_throttle_enabled'] } : {},
  }
}

/** Extract the JSON object from one native model_extra_config parse log line. */
export function parseTraeModelExtraConfigLogLine(line: string): TraeRawChatBehaviorConfig | undefined {
  const marker = ', raw: '
  const at = line.indexOf(marker)
  if (at === -1) return undefined
  const candidate = line.slice(at + marker.length).trim()
  try { return parseTraeRawChatBehaviorConfig(JSON.parse(candidate) as unknown) } catch { return undefined }
}
