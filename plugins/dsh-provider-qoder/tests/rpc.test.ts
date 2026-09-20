import test from 'node:test'
import assert from 'node:assert/strict'
import type { Context } from '@deepseek-ai/cordis'
import type { ConnectionRpcHandler } from '@deepseek-ai/dsh-client-connection'
import { createQoderRpcCaller } from '../src/client/rpc-client.ts'
import { isQoderRpcEndpoint, isQoderRpcErrorCode } from '../src/dsh/rpc-channel.ts'
import { registerQoderRpc, type QoderFetchRoute } from '../src/dsh/rpc.ts'

interface Capture {
  context: Context
  routes: QoderFetchRoute[]
  removed: string[]
}

/** Capture every route the host half registers, standing in for Connection. */
function captureConnection(): Capture {
  const routes: QoderFetchRoute[] = []
  const removed: string[] = []
  const context = {
    connection: {
      fetch: {
        register: (route: QoderFetchRoute) => {
          routes.push(route)
          return () => { removed.push(route.path) }
        },
      },
    },
  } as unknown as Context
  return { context, routes, removed }
}

function rpcRequest(path: string, body?: string): Request {
  return new Request(`http://127.0.0.1${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    ...body === undefined ? {} : { body },
  })
}

test('the settings RPC mounts both endpoints as POST routes below the shared API channel', () => {
  const { context, routes, removed } = captureConnection()
  const handler: ConnectionRpcHandler = async () => ({ ok: true, value: {} })

  const dispose = registerQoderRpc(context, handler)

  assert.deepEqual(routes.map(route => route.path), [
    '/api/qoder-subscription/account',
    '/api/qoder-subscription/models',
  ])
  assert.deepEqual(routes.map(route => [...route.methods]), [['POST'], ['POST']])
  assert.deepEqual(routes.map(route => route.requestBody), ['buffered', 'buffered'])
  assert.ok(routes.every(route => typeof route.fetch === 'function'))

  dispose()
  assert.deepEqual(removed, ['/api/qoder-subscription/account', '/api/qoder-subscription/models'])
})

test('a registered route decodes the request payload and encodes the handler result', async () => {
  const { context, routes } = captureConnection()
  const seen: Array<{ endpoint: string; payload: unknown }> = []
  registerQoderRpc(context, async (endpoint, payload) => {
    seen.push({ endpoint, payload })
    return { ok: true, value: { endpoint, plan: 'pro' } }
  })

  const account = await routes[0].fetch(rpcRequest('/api/qoder-subscription/account', JSON.stringify({ force: true })))
  assert.equal(account.status, 200)
  assert.deepEqual(await account.json(), { ok: true, value: { endpoint: 'account', plan: 'pro' } })

  const models = await routes[1].fetch(rpcRequest('/api/qoder-subscription/models'))
  assert.equal(models.status, 200)
  assert.deepEqual(seen, [
    { endpoint: 'account', payload: { force: true } },
    { endpoint: 'models', payload: {} },
  ])
})

test('a route keeps endpoint failures inside the envelope and reports bad requests', async () => {
  const { context, routes } = captureConnection()
  registerQoderRpc(context, async (endpoint) => {
    if (endpoint === 'models') {
      return { ok: false, error: { code: 'internal', message: 'no models', details: { issues: [] } } }
    }
    throw new Error('transport exploded')
  })

  const failure = await routes[1].fetch(rpcRequest('/api/qoder-subscription/models'))
  assert.equal(failure.status, 200)
  assert.deepEqual(await failure.json(), {
    ok: false,
    error: { code: 'internal', message: 'no models', details: { issues: [] } },
  })

  const crash = await routes[0].fetch(rpcRequest('/api/qoder-subscription/account'))
  assert.equal(crash.status, 500)
  assert.match(await crash.text(), /handler failure: Error: transport exploded/u)

  const malformed = await routes[0].fetch(rpcRequest('/api/qoder-subscription/account', 'not json'))
  assert.equal(malformed.status, 400)
  assert.equal(await malformed.text(), 'body is not JSON')
})

test('a route returns an ABORTED envelope when the request is aborted', async () => {
  const { context, routes } = captureConnection()
  registerQoderRpc(context, async () => ({ ok: true, value: {} }))

  const controller = new AbortController()
  controller.abort()
  const req = new Request('http://127.0.0.1/api/qoder-subscription/account', {
    method: 'POST',
    signal: controller.signal,
  })
  const response = await routes[0].fetch(req)
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), {
    ok: false,
    error: { code: 'ABORTED', message: 'Request aborted', details: { issues: [] } },
  })
})

test('the settings RPC reports an unavailable Connection fetch registry', () => {
  const handler: ConnectionRpcHandler = async () => ({ ok: true, value: {} })

  assert.throws(
    () => registerQoderRpc({} as Context, handler),
    /connection exposes no exact Fetch route registry/u,
  )
  assert.throws(
    () => registerQoderRpc({ connection: {} } as unknown as Context, handler),
    /connection exposes no exact Fetch route registry/u,
  )
})

test('isQoderRpcEndpoint recognizes valid endpoint names and rejects others', () => {
  assert.equal(isQoderRpcEndpoint('account'), true)
  assert.equal(isQoderRpcEndpoint('models'), true)
  assert.equal(isQoderRpcEndpoint('unknown'), false)
  assert.equal(isQoderRpcEndpoint(''), false)
  assert.equal(isQoderRpcEndpoint(null), false)
  assert.equal(isQoderRpcEndpoint(undefined), false)
  assert.equal(isQoderRpcEndpoint(123), false)
})

test('isQoderRpcErrorCode recognizes valid error codes and rejects others', () => {
  assert.equal(isQoderRpcErrorCode('NO_CREDENTIALS'), true)
  assert.equal(isQoderRpcErrorCode('UNAUTHENTICATED'), true)
  assert.equal(isQoderRpcErrorCode('UPSTREAM_ERROR'), true)
  assert.equal(isQoderRpcErrorCode('TIMEOUT'), true)
  assert.equal(isQoderRpcErrorCode('ABORTED'), true)
  assert.equal(isQoderRpcErrorCode('UNKNOWN_ENDPOINT'), true)
  assert.equal(isQoderRpcErrorCode('INTERNAL'), true)
  assert.equal(isQoderRpcErrorCode('INVALID_CODE'), false)
  assert.equal(isQoderRpcErrorCode(''), false)
  assert.equal(isQoderRpcErrorCode(null), false)
})

test('the browser caller posts to the shared API channel with the session cookie', async () => {
  const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = []
  const caller = createQoderRpcCaller({
    fetch: async (input, init) => {
      calls.push({ input, init })
      return Response.json({ ok: true, value: [{ id: 'cmodel' }] })
    },
  })
  const controller = new AbortController()

  const result = await caller.call('models', {}, controller.signal)

  assert.deepEqual(result, { ok: true, value: [{ id: 'cmodel' }] })
  assert.equal(String(calls[0].input), '/api/qoder-subscription/models')
  assert.equal(calls[0].init?.method, 'POST')
  assert.equal(calls[0].init?.credentials, 'include')
  assert.deepEqual(calls[0].init?.headers, { 'content-type': 'application/json' })
  assert.equal(calls[0].init?.body, '{}')
  assert.equal(calls[0].init?.signal, controller.signal)
})

test('the browser caller reports transport and endpoint failures without throwing', async () => {
  const unavailable = createQoderRpcCaller({ fetch: async () => new Response('', { status: 405 }) })
  assert.deepEqual(await unavailable.call('account', { force: true }), {
    ok: false,
    error: {
      code: 'UPSTREAM_ERROR',
      message: 'transport failure for /api/qoder-subscription/account: HTTP 405',
    },
  })

  const rejected = createQoderRpcCaller({ fetch: async () => Response.json({ ok: false, error: { code: 'NO_CREDENTIALS', message: 'no PAT' } }) })
  assert.deepEqual(await rejected.call('account', {}), {
    ok: false,
    error: { code: 'NO_CREDENTIALS', message: 'no PAT' },
  })

  const flatRejected = createQoderRpcCaller({ fetch: async () => Response.json({ ok: false, error: 'flat error' }) })
  assert.deepEqual(await flatRejected.call('account', {}), {
    ok: false,
    error: { code: 'INTERNAL', message: 'flat error' },
  })

  const errorless = createQoderRpcCaller({ fetch: async () => Response.json({ ok: false }) })
  assert.deepEqual(await errorless.call('account', {}), {
    ok: false,
    error: { code: 'INTERNAL', message: 'RPC returned error' },
  })

  const offline = createQoderRpcCaller({ fetch: async () => { throw new Error('Failed to fetch') } })
  assert.deepEqual(await offline.call('account', {}), {
    ok: false,
    error: { code: 'INTERNAL', message: 'Failed to fetch' },
  })

  const abortedController = new AbortController()
  abortedController.abort()
  const abortedCaller = createQoderRpcCaller({
    fetch: async () => {
      const err = new Error('The operation was aborted')
      err.name = 'AbortError'
      throw err
    },
  })
  assert.deepEqual(await abortedCaller.call('account', {}, abortedController.signal), {
    ok: false,
    error: { code: 'ABORTED', message: 'The operation was aborted' },
  })
})
