import { describe, expect, it, vi } from 'vitest'
import { TraeSoloRemoteCatalogClient } from '../src/solo-remote.ts'
import type { TraeCredential } from '../src/auth.ts'

const credential: TraeCredential = { accessToken: 'token', userId: 'uid', host: 'https://host', expiresAtMs: Date.now() + 1000, edition: 'solo', source: 'desktop' }

describe('TraeSoloRemoteCatalogClient', () => {
  it('parses model capabilities from the preferred solo_agent_remote group', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response(JSON.stringify({ code: 0, data: { list: [
      { function: 'solo_agent_remote', models: [{
        name: 'qwen3.8-max', display_name: 'Qwen3.8-Max', multimodal: true, max_mode: true,
        context_window_tokens: { dev: 200000, max: 1000000 },
        reasoning_effort_config: { support_thinking: true, options: ['light', 'high', 'extra_high'], default_level: 'high' },
        features: JSON.stringify({ consumption_rate: { enable: true, data: { rate: 1.5 } }, reasoning: { enable: true } }),
      }] },
      { function: 'solo_work_remote', models: [{ name: 'ignored' }] },
    ] } }), { status: 200 }))
    const client = new TraeSoloRemoteCatalogClient({ credential: async () => credential, fetchImpl: fetchImpl as unknown as typeof fetch })
    await expect(client.fetchModels()).resolves.toEqual([{
      id: 'qwen3.8-max', name: 'Qwen3.8-Max', multimodal: true,
      contextWindow: 200000, maxContextWindow: 1000000, creditMultiplier: 1.5,
      reasoningSupported: true,
      reasoning: { supported: ['low', 'high', 'xhigh'], defaultEffort: 'high' },
    }])
    expect(fetchImpl.mock.calls[0]?.[0]).toBe('https://solo.trae.cn/api/remote/v1/models?functions=solo_agent_remote,solo_work_remote')
  })

  it('fails clearly when the catalog response contains no usable models', async () => {
    const fetchImpl = vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => new Response(JSON.stringify({ code: 0, data: { list: [] } }), { status: 200 }))
    const client = new TraeSoloRemoteCatalogClient({ credential: async () => credential, fetchImpl: fetchImpl as unknown as typeof fetch })
    await expect(client.fetchModels()).rejects.toThrow(/contained no models/)
  })

  it('does not expose a chat or session API', () => {
    const client = new TraeSoloRemoteCatalogClient({ credential: async () => credential })
    expect('chat' in client).toBe(false)
  })
})
