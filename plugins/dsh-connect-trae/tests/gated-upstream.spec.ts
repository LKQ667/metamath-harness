import { describe, expect, it, vi } from 'vitest'
import { TraeGatedUpstreamClient } from '../src/gated-upstream.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

const success = (text: string) => ({ ok: true as const, response: new Response(text) })
function client(result: ReturnType<typeof success>): TraeUpstreamClient {
  return { chatStream: vi.fn(async () => result) }
}

describe('TraeGatedUpstreamClient', () => {
  it('uses SOLO only until Raw Chat capability is proven', async () => {
    const raw = client(success('raw')); const solo = client(success('solo'))
    const gated = new TraeGatedUpstreamClient({ raw, solo, capability: () => ({ available: false, reason: 'protocol', status: 400 }) })
    const result = await gated.chatStream('{}')
    expect(result.ok && await result.response.text()).toBe('solo')
    expect(raw.chatStream).not.toHaveBeenCalled()
  })

  it('uses Raw Chat when capability is available', async () => {
    const raw = client(success('raw')); const solo = client(success('solo'))
    const gated = new TraeGatedUpstreamClient({ raw, solo, capability: () => ({ available: true, contentType: 'text/event-stream' }) })
    const result = await gated.chatStream('{}')
    expect(result.ok && await result.response.text()).toBe('raw')
    expect(solo.chatStream).not.toHaveBeenCalled()
  })
})
