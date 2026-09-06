import { describe, expect, it, vi } from 'vitest'
import { prepareSoloBody, TraeSoloUpstreamClient } from '../src/solo.ts'
import { decodeTraeEvent } from '../src/sse.ts'
import type { TraeCredential } from '../src/auth.ts'
import type { TraeIdentity } from '../src/identity.ts'

const credential: TraeCredential = { accessToken: 'at', userId: 'uid', host: 'https://host', expiresAtMs: Date.now() + 1000, edition: 'solo', source: 'desktop' }
const identity: TraeIdentity = { edition: 'solo', machineId: 'machine', deviceId: 'device', appVersion: '0.1.43', platform: 'darwin' }

describe('Trae SOLO protocol', () => {
  it('converts OpenAI messages, model and tools to the evidenced SOLO format', () => {
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({
      model: 'glm-5.2', messages: [{ role: 'user', content: 'hello' }, { role: 'assistant', tool_calls: [{ id: '1', function: { name: 'read', arguments: '{}' } }] }],
      tools: [{ type: 'function', function: { name: 'read', parameters: { type: 'object' } } }], stream: false,
    })))
    expect(prepared).toMatchObject({ model: 'glm-5.2', config_name: 'glm-5.2', function: 'solo_work_lite', stream: true })
    expect(prepared.messages[0].content).toEqual([{ type: 'text', text: 'hello' }])
    expect(prepared.messages[1].tool_calls[0].function_call).toEqual({ name: 'read', arguments: '{}' })
    expect(prepared.messages[1].tool_calls[0].function).toBeUndefined()
    expect(prepared.tools[0].function.parameters).toBe('{"type":"object"}')
  })

  it('drops undeclared OpenAI parameters from minimal and tool-rich requests', () => {
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({
      model: 'Doubao-Seed-Code',
      messages: [{ role: 'developer', content: 'title' }, { role: 'user', content: 'name it' }],
      temperature: 0.2,
      max_tokens: 128,
      tool_choice: 'auto',
      parallel_tool_calls: true,
      response_format: { type: 'json_object' },
      user: 'session',
    })))
    expect(prepared).toEqual({
      messages: [
        { role: 'system', content: [{ type: 'text', text: 'title' }] },
        { role: 'user', content: [{ type: 'text', text: 'name it' }] },
      ],
      model: 'Doubao-Seed-Code',
      config_name: 'Doubao-Seed-Code',
      function: 'solo_work_lite',
      stream: true,
    })
  })

  it('keeps image content arrays unchanged while filtering the envelope', () => {
    const content = [
      { type: 'text', text: 'describe' },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,abc' } },
    ]
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({
      model: 'Doubao-Seed-Code', messages: [{ role: 'user', content }], temperature: 1,
    })))
    expect(prepared.messages[0].content).toEqual(content)
    expect(prepared).toMatchObject({ model: 'Doubao-Seed-Code', config_name: 'Doubao-Seed-Code' })
    expect(prepared).not.toHaveProperty('temperature')
  })

  it('passes the requested model id through unchanged as the llm_utils_chat wire id', () => {
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({ model: 'glm-5.2', messages: [] })))
    expect(prepared).toMatchObject({ model: 'glm-5.2', config_name: 'glm-5.2' })
  })

  it('normalises the DSH developer role to system for the Trae upstream', () => {
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({
      model: 'glm-5.2',
      messages: [
        { role: 'developer', content: 'You are a coding agent.' },
        { role: 'user', content: 'hi' },
      ],
    })))
    expect(prepared.messages[0]).toMatchObject({ role: 'system', content: [{ type: 'text', text: 'You are a coding agent.' }] })
  })

  it('preserves tool results for the next agent-loop turn', () => {
    const prepared = JSON.parse(prepareSoloBody(JSON.stringify({
      model: 'glm-5.2',
      messages: [
        { role: 'assistant', content: '', tool_calls: [{ id: 'call-1', type: 'function', function: { name: 'read', arguments: '{"file_path":"README.md"}' } }] },
        { role: 'tool', tool_call_id: 'call-1', content: 'file contents' },
      ],
    })))
    expect(prepared.messages[0].tool_calls[0].function_call.name).toBe('read')
    expect(prepared.messages[1]).toMatchObject({ role: 'tool', tool_call_id: 'call-1', content: [{ type: 'text', text: 'file contents' }] })
  })

  it('rejects tool results without a call id', () => {
    expect(() => prepareSoloBody(JSON.stringify({ messages: [{ role: 'tool', content: 'orphan' }] })))
      .toThrow('tool_call_id')
  })

  it('parses model discovery from the real get_detail_param field names', async () => {
    // Verified 2026-08-30: get_detail_param uses `model_detail_list[].prompt_max_tokens`
    // (context) and `max_tokens` (max output). There are no `max_input_tokens` /
    // `max_output_tokens` / `reasoning_effort_options` fields; reading those made
    // every row's context/maxTokens/reasoning undefined.
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response(JSON.stringify({ config_info_list: [{
      config_name: 'glm-5.2', display_config: { display_name: 'GLM-5.2' },
      context_window_tokens: { dev: 232768 },
      model_detail_list: [{ model_name: 'glm-5.2__dev', prompt_max_tokens: 168000, max_tokens: 32000 }],
    }] }), { status: 200, headers: { 'content-type': 'application/json' } }))
    const client = new TraeSoloUpstreamClient({ credential: async () => credential, identity: async () => identity, fetchImpl })
    await expect(client.fetchModels()).resolves.toEqual([{ id: 'glm-5.2', name: 'GLM-5.2', contextWindow: 168000, maxTokens: 32000 }])
    expect(fetchImpl.mock.calls[0]?.[0]).toBe('https://host/api/ide/v1/get_detail_param')
  })

  it('parses SOLO output, usage and reasoning tokens', () => {
    expect(decodeTraeEvent({ event: 'output', data: '{"response":"a","reasoning_content":"r","tool_calls":[{"index":0}]}' })).toEqual({ type: 'delta', text: 'a', reasoning: 'r', toolCalls: [{ index: 0 }] })
    expect(decodeTraeEvent({ event: 'token_usage', data: '{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5,"reasoning_tokens":2}' })).toEqual({ type: 'usage', inputTokens: 2, outputTokens: 3, totalTokens: 5, reasoningTokens: 2 })
  })

  it('calls only the evidenced llm_utils_chat endpoint with required headers', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response('event: done\ndata: {"finish_reason":"stop"}\n\n', { status: 200 }))
    const client = new TraeSoloUpstreamClient({ credential: async () => credential, identity: async () => identity, fetchImpl })
    const result = await client.chatStream(JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }))
    expect(result.ok).toBe(true)
    const [url, init] = fetchImpl.mock.calls[0]!
    expect(url).toBe('https://host/api/agent/v3/llm_utils_chat')
    const headers = init?.headers as Record<string, string>
    expect(headers['X-Ide-Token']).toBe('at')
    expect(headers['User-Agent']).toBe('Trae/0.1.43')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })
})
