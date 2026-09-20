import { createServer, request } from 'node:http'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { WorkBuddyCredentialStore } from '../src/auth.ts'
import { workBuddyStatusHandler } from '../src/web-status.ts'
import { WORKBUDDY_STATUS_PATH } from '../src/status-paths.ts'
import type { WorkBuddyStatusRouteOptions } from '../src/web-status.ts'
import type { WorkBuddyUpstreamModel } from '../src/upstream.ts'

const CLEANUP: (() => Promise<void>)[] = []

afterEach(async () => {
  await Promise.all(CLEANUP.splice(0).map(clean => clean()))
})

function nestedDoc(expiresAt: number): string {
  return JSON.stringify({
    auth: { accessToken: 'at', refreshToken: 'rt', expiresAt, domain: 'www.codebuddy.cn' },
    account: { uid: 'uid-1', nickname: '昵称' },
  })
}

/** Raw HTTP request with full header control (fetch forbids overriding Host). */
function requestOnce(options: {
  port: number
  method: string
  headers: Record<string, string>
}): Promise<{ status: number, body: string }> {
  return new Promise((resolve, reject) => {
    const outgoing = request({
      host: '127.0.0.1',
      port: options.port,
      method: options.method,
      path: WORKBUDDY_STATUS_PATH,
      headers: options.headers,
    }, (res) => {
      const chunks: Buffer[] = []
      res.on('data', (chunk: Buffer) => chunks.push(chunk))
      res.on('end', () => resolve({
        status: res.statusCode ?? 0,
        body: Buffer.concat(chunks).toString('utf8'),
      }))
    })
    outgoing.on('error', reject)
    outgoing.end()
  })
}

async function startStatusServer(overrides: Partial<WorkBuddyStatusRouteOptions> = {}): Promise<number> {
  const dir = await mkdtemp(join(tmpdir(), 'wb-status-'))
  CLEANUP.push(() => rm(dir, { recursive: true, force: true }))
  const desktop = join(dir, 'workbuddy-desktop.info')
  await writeFile(desktop, nestedDoc(Date.now() + 3600_000))
  const deps: WorkBuddyStatusRouteOptions = {
    store: new WorkBuddyCredentialStore({
      desktopPath: desktop,
      ownPath: join(dir, 'own.json'),
      refresh: async credential => ({ accessToken: credential.accessToken }),
    }),
    client: { fetchCredits: async () => ({ total: 0, accounts: [] }) },
    models: () => [],
    ...overrides,
  }
  const server = createServer(workBuddyStatusHandler(deps))
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const { port } = server.address() as { port: number }
  CLEANUP.push(() => new Promise<void>(resolve => server.close(() => resolve())))
  return port
}

describe('context capacity reporting', () => {
  /**
   * The card needs every model's capacity, not only the promoted ones: the
   * models where capacity matters (a 200k model beside 1M siblings) carry no
   * promo, so a payload filtered down to discounts would hide exactly the fact
   * worth showing. The discount list filters at render time instead.
   */
  it('reports capacity for un-promoted models, verbatim and unfiltered', async () => {
    const port = await startStatusServer({
      models: (): readonly WorkBuddyUpstreamModel[] => [
        {
          id: 'glm-5.1', name: 'GLM-5.1', contextWindow: 200_000, maxTokens: 48_000, supportsImages: false,
          reasoning: { supports: true, onlyReasoning: true, canDisableThinking: false },
          billing: { credits: 'x0.79 credits', free: false },
        },
        {
          id: 'hy3', name: 'Hy3', contextWindow: 192_000, maxTokens: 64_000, supportsImages: true,
          reasoning: { supports: true, onlyReasoning: true, canDisableThinking: false },
          billing: { credits: 'x0.00', free: true, badges: ['限时免费'] },
        },
        {
          id: 'plain', name: 'Plain', contextWindow: 1_000_000, maxTokens: 32_000, supportsImages: true,
          reasoning: { supports: true, onlyReasoning: true, canDisableThinking: false },
          billing: { free: false },
        },
      ],
    })
    const response = await requestOnce({ port, method: 'GET', headers: { host: `127.0.0.1:${String(port)}` } })
    const body = JSON.parse(response.body) as { models?: readonly { id: string; contextWindow?: number }[] }
    const models = body.models ?? []
    // Verbatim from upstream: no rounding, and no tier of the plugin's own.
    expect(models.find(model => model.id === 'glm-5.1')?.contextWindow).toBe(200_000)
    expect(models.find(model => model.id === 'hy3')?.contextWindow).toBe(192_000)
    // A model with no promo and no rate is still reported: capacity is the one
    // fact the card needs for every model, not just the discounted ones.
    expect(models.find(model => model.id === 'plain')?.contextWindow).toBe(1_000_000)
  })

  it('omits capacity when the upstream number is not usable', async () => {
    const port = await startStatusServer({
      models: (): readonly WorkBuddyUpstreamModel[] => [
        {
          id: 'broken', name: 'Broken', contextWindow: 0, maxTokens: 1_000, supportsImages: false,
          reasoning: { supports: true, onlyReasoning: true, canDisableThinking: false },
          billing: { free: false },
        },
      ],
    })
    const response = await requestOnce({ port, method: 'GET', headers: { host: `127.0.0.1:${String(port)}` } })
    const body = JSON.parse(response.body) as { models?: readonly { id: string; contextWindow?: number }[] }
    // A non-positive capacity is not reported rather than shown as "0".
    expect(body.models?.find(model => model.id === 'broken')?.contextWindow).toBeUndefined()
  })
})

describe('web status route gate', () => {
  it('serves a same-origin GET without an Origin header', async () => {
    const port = await startStatusServer()
    const response = await requestOnce({ port, method: 'GET', headers: { host: `127.0.0.1:${String(port)}` } })
    expect(response.status).toBe(200)
    expect(JSON.parse(response.body)).toMatchObject({ status: 'signed-in', nickname: '昵称' })
  })

  it('accepts localhost hosts and explicit loopback Origins', async () => {
    const port = await startStatusServer()
    const viaLocalhost = await requestOnce({ port, method: 'GET', headers: { host: `localhost:${String(port)}` } })
    expect(viaLocalhost.status).toBe(200)
    const viaOrigin = await requestOnce({
      port,
      method: 'GET',
      headers: { host: `127.0.0.1:${String(port)}`, origin: `http://127.0.0.1:${String(port)}` },
    })
    expect(viaOrigin.status).toBe(200)
  })

  it('drops a DNS-rebinding style request whose Host is not loopback', async () => {
    const port = await startStatusServer()
    const response = await requestOnce({ port, method: 'GET', headers: { host: 'evil.example:3080' } })
    expect(response.status).toBe(403)
  })

  it('drops a request whose Origin is not loopback even on a loopback Host', async () => {
    const port = await startStatusServer()
    const response = await requestOnce({
      port,
      method: 'GET',
      headers: { host: `127.0.0.1:${String(port)}`, origin: 'http://evil.example' },
    })
    expect(response.status).toBe(403)
  })

  it('answers 405 for non-GET methods', async () => {
    const port = await startStatusServer()
    const response = await requestOnce({ port, method: 'POST', headers: { host: `127.0.0.1:${String(port)}` } })
    expect(response.status).toBe(405)
  })
})
