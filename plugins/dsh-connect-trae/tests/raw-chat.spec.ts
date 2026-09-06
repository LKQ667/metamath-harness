import { describe, expect, it } from 'vitest'
import { buildTraeRawChatDraft, decodeRawChatChunk, TRAE_RAW_CHAT_V1_PATH, TRAE_RAW_CHAT_V2_PATH } from '../src/raw-chat.ts'

describe('Trae raw-chat evidence model', () => {
  it('keeps v1 and v2 explicit instead of blind fallback', () => {
    expect(TRAE_RAW_CHAT_V2_PATH).toBe('/api/ide/v2/llm_raw_chat')
    expect(TRAE_RAW_CHAT_V1_PATH).toBe('/api/ide/v1/llm_raw_chat')
  })

  it('builds an offline OpenAI-like draft without mutating inputs', () => {
    const messages = [{ role: 'user' as const, content: 'hello' }]
    const body = buildTraeRawChatDraft({ model: 'glm-5.2', messages, maxTokens: 100, temperature: 0.2 })
    expect(body).toEqual({ model: 'glm-5.2', messages, stream: true, max_tokens: 100, temperature: 0.2 })
    expect(() => buildTraeRawChatDraft({ model: '', messages })).toThrow(/model/)
    expect(() => buildTraeRawChatDraft({ model: 'm', messages: [] })).toThrow(/messages/)
  })

  it('adds only explicit reasoning and safe runtime extra info', () => {
    const messages = [{ role: 'user' as const, content: 'hello' }]
    const body = buildTraeRawChatDraft({
      model: 'qwen-3.7-plus', messages, reasoningEffort: 'high',
      extraInfo: { native_function_call: true, use_v2_process: true, max_mode_enabled: false },
    })
    expect(body).toMatchObject({
      reasoning_effort: 'high',
      extra_info: { native_function_call: true, use_v2_process: true, max_mode_enabled: false },
    })
  })

  it('decodes text, reasoning, tool calls, usage and finish reason', () => {
    expect(decodeRawChatChunk({
      choices: [{ delta: {
        reasoning_content: 'think', content: 'answer',
        tool_calls: [{ index: 0, id: 'call-1', function: { name: 'read', arguments: '{"path":"a"}' } }],
      }, finish_reason: 'tool_calls' }],
      usage: { prompt_tokens: 10, completion_tokens: 4, total_tokens: 14 },
    })).toEqual([
      { type: 'reasoning', text: 'think' },
      { type: 'text', text: 'answer' },
      { type: 'tool-call', index: 0, id: 'call-1', name: 'read', arguments: '{"path":"a"}' },
      { type: 'done', finishReason: 'tool_calls' },
      { type: 'usage', inputTokens: 10, outputTokens: 4, totalTokens: 14 },
    ])
  })

  it('handles DONE and preserves unknown payloads', () => {
    expect(decodeRawChatChunk('[DONE]')).toEqual([{ type: 'done', finishReason: 'stop' }])
    expect(decodeRawChatChunk({ strange: true })).toEqual([{ type: 'unknown', value: { strange: true } }])
  })
})
