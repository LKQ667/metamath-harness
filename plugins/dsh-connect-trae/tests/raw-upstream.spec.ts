import { describe, expect, it, vi } from 'vitest'
import { classifyTraeRawChatFailure, TraeRawChatUpstreamClient } from '../src/raw-upstream.ts'
import type { TraeCredential } from '../src/auth.ts'
import type { TraeIdentity } from '../src/identity.ts'

const credential: TraeCredential = { accessToken: 'at', userId: 'uid', host: 'https://host', expiresAtMs: Date.now() + 1000, edition: 'cn', source: 'desktop' }
const identity: TraeIdentity = { edition: 'cn', machineId: 'machine', deviceId: 'device', platform: 'darwin' }
const config = { model: 'glm-5.2', configName: 'glm-5.2', promptSet: 'chat_completion', abVersion: 'test-ab', passBackReasoning: true }

describe('TraeRawChatUpstreamClient', () => {
  it('classifies redacted probe failures without exposing message content', () => {
    expect(classifyTraeRawChatFailure('')).toBe('empty')
    expect(classifyTraeRawChatFailure('{"code":400}')).toBe('json')
    expect(classifyTraeRawChatFailure('missing required field')).toBe('schema')
    expect(classifyTraeRawChatFailure('permission denied')).toBe('permission')
    expect(classifyTraeRawChatFailure('unknown model config_name')).toBe('model')
    expect(classifyTraeRawChatFailure('Trae Raw Chat returned HTTP 400')).toBe('generic-http')
    expect(classifyTraeRawChatFailure('bad gateway')).toBe('other')
  })
  it('requires an evidence-backed config name but permits observed None optionals', () => {
    expect(() => new TraeRawChatUpstreamClient({ credential: async () => credential, identity: async () => identity, config: { ...config, configName: '' } })).toThrow(/configName/)
    expect(() => new TraeRawChatUpstreamClient({ credential: async () => credential, identity: async () => identity, config: { model: 'glm-5.2', configName: 'glm-5.2', passBackReasoning: true } })).not.toThrow()
  })

  it('posts only v2 with config fields and returns the live response', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response('data: [DONE]\n\n', { status: 200, headers: { 'content-type': 'text/event-stream' } }))
    const client = new TraeRawChatUpstreamClient({ credential: async () => credential, identity: async () => identity, config, fetchImpl })
    const result = await client.chatStream(JSON.stringify({ messages: [{ role: 'user', content: 'hi' }], max_tokens: 8 }))
    expect(result.ok).toBe(true)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    const [url, init] = fetchImpl.mock.calls[0]!
    expect(url).toBe('https://host/api/ide/v2/llm_raw_chat')
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>
    expect(body).toMatchObject({ model: 'glm-5.2', stream: true, config_name: 'glm-5.2', prompt_set: 'chat_completion', ab_version: 'test-ab', pass_back_reasoning: true })
  })

  it('projects runtime behavior and request reasoning into the Raw Chat body', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response('data: [DONE]\n\n', { status: 200 }))
    const client = new TraeRawChatUpstreamClient({
      credential: async () => credential,
      identity: async () => identity,
      config: {
        model: 'qwen-3.7-plus', configName: 'qwen-3.7-plus', passBackReasoning: false,
        runtime: {
          configName: 'qwen-3.7-plus', modelName: 'qwen-3.7-plus', passBackReasoning: true,
          nativeFunctionCall: true, useV2Process: true, maxModeEnabled: false,
        },
      },
      fetchImpl,
    })
    await client.chatStream(JSON.stringify({ messages: [{ role: 'user', content: 'hi' }], reasoning_effort: 'high' }))
    const body = JSON.parse(String(fetchImpl.mock.calls[0]?.[1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      reasoning_effort: 'high', pass_back_reasoning: true,
      extra_info: { native_function_call: true, use_v2_process: true, v2_max_mode_enabled: false },
    })
  })

  it('classifies upstream errors without exposing request credentials', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response('', { status: 400 }))
    const client = new TraeRawChatUpstreamClient({ credential: async () => credential, identity: async () => identity, config, fetchImpl })
    await expect(client.chatStream(JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }))).resolves.toEqual({
      ok: false, status: 400, kind: 'client', message: 'Trae Raw Chat returned HTTP 400',
    })
  })

  it('rejects malformed local requests without network access', async () => {
    const fetchImpl = vi.fn()
    const client = new TraeRawChatUpstreamClient({ credential: async () => credential, identity: async () => identity, config, fetchImpl: fetchImpl as unknown as typeof fetch })
    await expect(client.chatStream('{')).resolves.toMatchObject({ ok: false, status: 400 })
    expect(fetchImpl).not.toHaveBeenCalled()
  })
})
