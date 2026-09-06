import { describe, expect, it, vi } from 'vitest'
import { TraeFallbackUpstreamClient } from '../src/fallback-upstream.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

function client(result: Awaited<ReturnType<TraeUpstreamClient['chatStream']>>): TraeUpstreamClient {
  return { chatStream: vi.fn(async () => result) }
}

describe('TraeFallbackUpstreamClient', () => {
  it.each([400, 404, 415])('falls back on pre-stream protocol HTTP %s', async status => {
    const primary = client({ ok: false, status, kind: status === 404 ? 'not_found' : 'client', message: 'incompatible' })
    const response = new Response('fallback')
    const fallback = client({ ok: true, response })
    const onFallback = vi.fn()
    const composed = new TraeFallbackUpstreamClient({ primary, fallback, onFallback })
    await expect(composed.chatStream('{}')).resolves.toEqual({ ok: true, response })
    expect(fallback.chatStream).toHaveBeenCalledTimes(1)
    expect(onFallback).toHaveBeenCalledTimes(1)
  })

  it.each([
    { status: 401, kind: 'authentication' as const },
    { status: 402, kind: 'hard_credit' as const },
    { status: 429, kind: 'soft_rate' as const },
    { status: 500, kind: 'server' as const },
  ])('does not replay $kind failures', async failure => {
    const result = { ok: false as const, ...failure, message: 'stop' }
    const primary = client(result)
    const fallback = client({ ok: true, response: new Response('must not run') })
    const composed = new TraeFallbackUpstreamClient({ primary, fallback })
    await expect(composed.chatStream('{}')).resolves.toEqual(result)
    expect(fallback.chatStream).not.toHaveBeenCalled()
  })

  it('never falls back after primary returned a response, even if its body later fails', async () => {
    const response = new Response(new ReadableStream({ start(controller) { controller.error(new Error('mid-stream')) } }))
    const primary = client({ ok: true, response })
    const fallback = client({ ok: true, response: new Response('must not run') })
    const composed = new TraeFallbackUpstreamClient({ primary, fallback })
    await expect(composed.chatStream('{}')).resolves.toEqual({ ok: true, response })
    expect(fallback.chatStream).not.toHaveBeenCalled()
  })

  it('does not fall back after cancellation', async () => {
    const primary = client({ ok: false, status: 400, kind: 'client', message: 'cancelled' })
    const fallback = client({ ok: true, response: new Response('must not run') })
    const controller = new AbortController(); controller.abort()
    const composed = new TraeFallbackUpstreamClient({ primary, fallback })
    await composed.chatStream('{}', controller.signal)
    expect(fallback.chatStream).not.toHaveBeenCalled()
  })
})
