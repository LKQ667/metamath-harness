import { request } from 'node:http'
import { afterEach, describe, expect, it } from 'vitest'
import { TraeCatalog } from '../src/catalog.ts'
import { createTraeShim, type TraeShim } from '../src/shim.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

const cleanup: TraeShim[] = []
afterEach(async () => { await Promise.all(cleanup.splice(0).map(shim => shim.close())) })

async function start(client?: TraeUpstreamClient): Promise<TraeShim> {
  const shim = createTraeShim({
    catalog: new TraeCatalog(),
    client: client ?? new (await import('../src/upstream.ts')).UnconfiguredTraeUpstreamClient(),
  })
  await shim.ready
  cleanup.push(shim)
  return shim
}

function raw(port: number, options: { method?: string; path?: string; headers?: Record<string, string>; body?: string }) {
  return new Promise<{ status: number; body: string }>((resolve, reject) => {
    const req = request({ host: '127.0.0.1', port, method: options.method ?? 'GET', path: options.path ?? '/', headers: options.headers }, res => {
      const chunks: Buffer[] = []
      res.on('data', chunk => chunks.push(chunk))
      res.on('end', () => resolve({ status: res.statusCode ?? 0, body: Buffer.concat(chunks).toString('utf8') }))
    })
    req.on('error', reject)
    if (options.body !== undefined) req.write(options.body)
    req.end()
  })
}

describe('Trae loopback shim', () => {
  it('binds an ephemeral loopback port and serves models with the secret', async () => {
    const shim = await start()
    expect(shim.baseUrl()).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/)
    const response = await fetch(`${shim.baseUrl()}/v1/models`, { headers: { authorization: `Bearer ${shim.token()}` } })
    expect(response.status).toBe(200)
    const body = await response.json() as { data: { id: string }[] }
    expect(body.data.map(item => item.id)).toContain('auto')
  })

  it('rejects missing bearer and hostile Host', async () => {
    const shim = await start()
    const port = Number(new URL(shim.baseUrl()).port)
    const missing = await raw(port, { path: '/healthz', headers: { host: `127.0.0.1:${port}` } })
    expect(missing.status).toBe(401)
    const hostile = await raw(port, { path: '/healthz', headers: { host: 'evil.example', authorization: `Bearer ${shim.token()}` } })
    expect(hostile.status).toBe(403)
  })

  it('rejects hostile Origin and non-JSON chat', async () => {
    const shim = await start()
    const port = Number(new URL(shim.baseUrl()).port)
    const origin = await raw(port, {
      method: 'POST', path: '/v1/chat/completions',
      headers: { host: `127.0.0.1:${port}`, origin: 'https://evil.example', 'content-type': 'application/json', authorization: `Bearer ${shim.token()}` },
      body: '{}',
    })
    expect(origin.status).toBe(403)
    const contentType = await raw(port, {
      method: 'POST', path: '/v1/chat/completions',
      headers: { host: `127.0.0.1:${port}`, 'content-type': 'text/plain', authorization: `Bearer ${shim.token()}` },
      body: '{}',
    })
    expect(contentType.status).toBe(415)
  })

  it('returns an explicit 503 while the real protocol is disabled', async () => {
    const shim = await start()
    const response = await fetch(`${shim.baseUrl()}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${shim.token()}` },
      body: JSON.stringify({ model: 'auto', messages: [] }),
    })
    expect(response.status).toBe(503)
    expect(await response.text()).toContain('protocol is not configured')
  })

  it('aborts upstream when the inbound request closes', async () => {
    let seenSignal: AbortSignal | undefined
    let enteredResolve!: () => void
    const entered = new Promise<void>(resolve => { enteredResolve = resolve })
    const shim = await start({
      async chatStream(_body, signal) {
        seenSignal = signal
        enteredResolve()
        await new Promise(resolve => setTimeout(resolve, 100))
        return { ok: false, status: 503, kind: 'unconfigured', message: 'late' }
      },
    })
    const port = Number(new URL(shim.baseUrl()).port)
    const req = request({ host: '127.0.0.1', port, method: 'POST', path: '/v1/chat/completions', headers: { host: `127.0.0.1:${port}`, 'content-type': 'application/json', authorization: `Bearer ${shim.token()}` } })
    req.on('error', () => {})
    req.write('{}')
    req.end()
    await entered
    req.destroy()
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(seenSignal?.aborted).toBe(true)
  })
})
