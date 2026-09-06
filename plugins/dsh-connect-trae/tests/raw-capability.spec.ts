import { describe, expect, it, vi } from 'vitest'
import { probeTraeRawChatCapability } from '../src/raw-capability.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

describe('Raw Chat capability probe', () => {
  it('accepts a successful response and cancels its diagnostic body', async () => {
    let cancelled = false
    const response = new Response(new ReadableStream({ cancel() { cancelled = true } }), { headers: { 'content-type': 'text/event-stream' } })
    const client = { chatStream: vi.fn(async () => ({ ok: true as const, response })) } satisfies TraeUpstreamClient
    await expect(probeTraeRawChatCapability(client)).resolves.toEqual({ available: true, contentType: 'text/event-stream' })
    expect(cancelled).toBe(true)
  })

  it.each([
    [{ ok: false as const, status: 400, kind: 'client' as const, message: '' }, 'protocol'],
    [{ ok: false as const, status: 401, kind: 'authentication' as const, message: '' }, 'authentication'],
    [{ ok: false as const, status: 402, kind: 'hard_credit' as const, message: '' }, 'credit'],
    [{ ok: false as const, status: 429, kind: 'soft_rate' as const, message: '' }, 'rate'],
    [{ ok: false as const, status: 0, kind: 'server' as const, message: '' }, 'transport'],
    [{ ok: false as const, status: 500, kind: 'server' as const, message: '' }, 'server'],
  ])('classifies unavailable capability without throwing', async (failure, reason) => {
    const client = { chatStream: vi.fn(async () => failure) } satisfies TraeUpstreamClient
    await expect(probeTraeRawChatCapability(client)).resolves.toEqual({ available: false, reason, status: failure.status })
  })
})
