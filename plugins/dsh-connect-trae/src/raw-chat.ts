export const TRAE_RAW_CHAT_V2_PATH = '/api/ide/v2/llm_raw_chat'
export const TRAE_RAW_CHAT_V1_PATH = '/api/ide/v1/llm_raw_chat'

export type RawChatRole = 'assistant' | 'system' | 'tool' | 'user'

export interface RawChatTextContent {
  type: 'text'
  text: string
}

export interface RawChatImageContent {
  type: 'image_url'
  image_url: { url: string }
}

export type RawChatContent = RawChatTextContent | RawChatImageContent

export interface RawChatToolCall {
  id: string
  type: 'function'
  function: { name: string; arguments: string }
}

export interface RawChatMessage {
  role: RawChatRole
  content: string | RawChatContent[]
  tool_call_id?: string
  tool_calls?: RawChatToolCall[]
}

export interface RawChatTool {
  type: 'function'
  function: {
    name: string
    description?: string
    parameters: Record<string, unknown>
  }
}

export interface TraeRawChatDraft {
  model: string
  messages: RawChatMessage[]
  stream: true
  tools?: RawChatTool[]
  max_tokens?: number
  temperature?: number
  reasoning_effort?: string
  extra_info?: Record<string, unknown>
}

/**
 * Evidence-bounded OpenAI-like draft inferred from Trae's LLMRaw* DTO symbols.
 * Pure/offline only: the upstream remains disabled until one controlled probe.
 */
export function buildTraeRawChatDraft(input: {
  model: string
  messages: readonly RawChatMessage[]
  tools?: readonly RawChatTool[]
  maxTokens?: number
  temperature?: number
  reasoningEffort?: string
  extraInfo?: Record<string, unknown>
}): TraeRawChatDraft {
  if (input.model.trim() === '') throw new Error('Trae raw chat requires a model')
  if (input.messages.length === 0) throw new Error('Trae raw chat requires messages')
  return {
    model: input.model,
    messages: structuredClone([...input.messages]),
    stream: true,
    ...input.tools === undefined || input.tools.length === 0 ? {} : { tools: structuredClone([...input.tools]) },
    ...input.maxTokens === undefined ? {} : { max_tokens: input.maxTokens },
    ...input.temperature === undefined ? {} : { temperature: input.temperature },
    ...input.reasoningEffort === undefined ? {} : { reasoning_effort: input.reasoningEffort },
    ...input.extraInfo === undefined ? {} : { extra_info: structuredClone(input.extraInfo) },
  }
}

export type RawChatDelta =
  | { type: 'text'; text: string }
  | { type: 'reasoning'; text: string }
  | { type: 'tool-call'; index: number; id?: string; name?: string; arguments?: string }
  | { type: 'usage'; inputTokens?: number; outputTokens?: number; totalTokens?: number }
  | { type: 'done'; finishReason: string }
  | { type: 'unknown'; value: unknown }

/** Decode OpenAI-like raw-chat chunks while preserving unknown structures. */
export function decodeRawChatChunk(value: unknown): RawChatDelta[] {
  if (value === '[DONE]') return [{ type: 'done', finishReason: 'stop' }]
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return [{ type: 'unknown', value }]
  const record = value as Record<string, unknown>
  const result: RawChatDelta[] = []
  const choices = Array.isArray(record['choices']) ? record['choices'] : []
  for (const rawChoice of choices) {
    if (typeof rawChoice !== 'object' || rawChoice === null) continue
    const choice = rawChoice as Record<string, unknown>
    const delta = typeof choice['delta'] === 'object' && choice['delta'] !== null ? choice['delta'] as Record<string, unknown> : {}
    if (typeof delta['reasoning_content'] === 'string' && delta['reasoning_content'] !== '') result.push({ type: 'reasoning', text: delta['reasoning_content'] })
    if (typeof delta['content'] === 'string' && delta['content'] !== '') result.push({ type: 'text', text: delta['content'] })
    if (Array.isArray(delta['tool_calls'])) {
      for (const rawTool of delta['tool_calls']) {
        if (typeof rawTool !== 'object' || rawTool === null) continue
        const tool = rawTool as Record<string, unknown>
        const fn = typeof tool['function'] === 'object' && tool['function'] !== null ? tool['function'] as Record<string, unknown> : {}
        result.push({
          type: 'tool-call',
          index: typeof tool['index'] === 'number' ? tool['index'] : 0,
          ...typeof tool['id'] === 'string' ? { id: tool['id'] } : {},
          ...typeof fn['name'] === 'string' ? { name: fn['name'] } : {},
          ...typeof fn['arguments'] === 'string' ? { arguments: fn['arguments'] } : {},
        })
      }
    }
    if (typeof choice['finish_reason'] === 'string' && choice['finish_reason'] !== '') result.push({ type: 'done', finishReason: choice['finish_reason'] })
  }
  if (typeof record['usage'] === 'object' && record['usage'] !== null) {
    const usage = record['usage'] as Record<string, unknown>
    result.push({
      type: 'usage',
      ...typeof usage['prompt_tokens'] === 'number' ? { inputTokens: usage['prompt_tokens'] } : {},
      ...typeof usage['completion_tokens'] === 'number' ? { outputTokens: usage['completion_tokens'] } : {},
      ...typeof usage['total_tokens'] === 'number' ? { totalTokens: usage['total_tokens'] } : {},
    })
  }
  return result.length === 0 ? [{ type: 'unknown', value }] : result
}
