import { describe, expect, it, vi } from 'vitest'
import { TraeDelegatingUpstreamClient } from '../src/delegating-upstream.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

const client = (text: string): TraeUpstreamClient => ({ chatStream: vi.fn(async () => ({ ok: true as const, response: new Response(text) })) })

describe('TraeDelegatingUpstreamClient', () => {
  it('uses its initial delegate and atomically replaces future calls', async () => {
    const initial = client('solo'); const replacement = client('gateway')
    const delegating = new TraeDelegatingUpstreamClient(initial)
    const first = await delegating.chatStream('{}')
    expect(first.ok && await first.response.text()).toBe('solo')
    delegating.replace(replacement)
    const second = await delegating.chatStream('{}')
    expect(second.ok && await second.response.text()).toBe('gateway')
  })

  it('keeps in-flight calls bound to the delegate selected at call time', async () => {
    let release!: (value: Awaited<ReturnType<TraeUpstreamClient['chatStream']>>) => void
    const initial: TraeUpstreamClient = { chatStream: () => new Promise(resolve => { release = resolve; release({ ok: true, response: new Response('solo') }) }) }
    const replacement = client('gateway'); const delegating = new TraeDelegatingUpstreamClient(initial)
    const inflight = delegating.chatStream('{}'); delegating.replace(replacement); release({ ok: true, response: new Response('solo') })
    const result = await inflight
    expect(result.ok && await result.response.text()).toBe('solo')
  })
})
