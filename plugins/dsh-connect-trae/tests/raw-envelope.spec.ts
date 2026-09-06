import { describe, expect, it } from 'vitest'
import { buildTraeRawChatDraft } from '../src/raw-chat.ts'
import { buildTraeFusionRawChatEnvelope, hashTraeRawChatArg } from '../src/raw-envelope.ts'

describe('Trae fusion Raw Chat envelope candidate', () => {
  it('is deterministic and preserves the OpenAI core body', () => {
    const arg = buildTraeRawChatDraft({ model: 'qwen-3.7-plus', messages: [{ role: 'user', content: 'OK' }] })
    const first = buildTraeFusionRawChatEnvelope(arg, { config_name: 'qwen-3.7-plus', pass_back_reasoning: true })
    const second = buildTraeFusionRawChatEnvelope(arg, { config_name: 'qwen-3.7-plus', pass_back_reasoning: true })
    expect(first).toEqual(second)
    expect(first.arg).toEqual(arg)
    expect(first.args_hash).toMatch(/^[a-f0-9]{64}$/)
    expect(first.args_hash).toBe(hashTraeRawChatArg(arg))
    expect(JSON.parse(first.config_json)).toEqual({ config_name: 'qwen-3.7-plus', pass_back_reasoning: true })
  })
})
