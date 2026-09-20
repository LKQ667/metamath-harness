/**
 * Loopback settings RPC for the Qoder cards.
 *
 * The endpoints ride on Connection's shared `/api` channel as exact Fetch
 * routes rather than as a dedicated `connection.rpc.handle` channel.
 *
 * `rpc.handle` resolves `webServer` on the connection plugin's own context. Up
 * to `dsh-client-connection` 0.1.2-rc.1 that context injected `webServer`, but
 * 0.1.5-rc.2 injects only `credentials` and moves `webServer` into a child
 * context, so every `rpc.handle` call now fails with `cannot get property
 * "webServer" without inject` and the channel is never mounted — which surfaces
 * in the browser as `HTTP 405` from the static frontend fallback. Exact Fetch
 * routes are registered in the service's own registry, never touch that lookup,
 * and are what DSH's own file-upload plugin uses.
 */

import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-connection'
import type { ConnectionRpcHandler } from '@deepseek-ai/dsh-client-connection'
import { qoderRpcEndpoints, qoderRpcPath, type QoderRpcEndpoint } from './rpc-channel.ts'

/**
 * One exact Fetch route as Connection exposes it.
 *
 * The released peer declarations still restrict exact routes to `GET`/`HEAD`
 * without a body mode, while the runtime accepts browser-driven `POST` routes
 * (DSH's own `/api/session/uploadFileBinary` is one). The shape is therefore
 * restated here instead of imported from the peer types.
 */
export interface QoderFetchRoute {
  path: string
  methods: readonly string[]
  requestBody: 'buffered' | 'streaming'
  fetch: (request: Request) => Promise<Response>
}

interface QoderFetchRegistry {
  register(route: QoderFetchRoute): unknown
}

/** The part of the Connection service this module depends on. */
export interface QoderRpcConnection {
  fetch?: QoderFetchRegistry
}

/**
 * Mount every Qoder settings endpoint on the shared API channel.
 *
 * Registering is caller-owned: the returned disposer removes the routes again,
 * so the caller can tie them to its fiber with `ctx.effect`.
 *
 * @param ctx - host context carrying the Connection service.
 * @param handler - decoded endpoint handler, shared by every endpoint.
 * @returns disposer removing every registered route.
 * @throws when Connection exposes no exact Fetch registry.
 */
export function registerQoderRpc(ctx: Context, handler: ConnectionRpcHandler): () => void {
  // The peer declaration narrows exact routes to GET/HEAD, so the service is
  // read through this module's shape instead of its own.
  const registry = (ctx as Context & { connection?: QoderRpcConnection }).connection?.fetch
  if (typeof registry?.register !== 'function') {
    throw new Error('provider-qoder: connection exposes no exact Fetch route registry')
  }
  const disposers = qoderRpcEndpoints.map(endpoint => registry.register({
    path: qoderRpcPath(endpoint),
    methods: ['POST'],
    requestBody: 'buffered',
    fetch: request => handleQoderRpcRequest(endpoint, handler, request),
  }))
  return () => {
    for (const dispose of disposers) {
      if (typeof dispose === 'function') (dispose as () => unknown)()
    }
  }
}

/**
 * Decode one request, run the endpoint handler, and encode its result.
 *
 * Failures stay inside the response envelope so the client keeps a single error
 * path; only a malformed body and a handler crash use a transport status.
 */
async function handleQoderRpcRequest(
  endpoint: QoderRpcEndpoint,
  handler: ConnectionRpcHandler,
  request: Request,
): Promise<Response> {
  if (request.signal.aborted) {
    return Response.json({
      ok: false,
      error: { code: 'ABORTED', message: 'Request aborted', details: { issues: [] } },
    })
  }
  let payload: unknown = {}
  const body = await request.text()
  if (body.trim().length > 0) {
    try {
      payload = JSON.parse(body)
    } catch {
      return new Response('body is not JSON', { status: 400 })
    }
  }
  try {
    return Response.json(await handler(endpoint, payload, request.signal))
  } catch (error) {
    if (request.signal.aborted) {
      return Response.json({
        ok: false,
        error: { code: 'ABORTED', message: 'Request aborted', details: { issues: [] } },
      })
    }
    return new Response(`handler failure: ${String(error)}`, { status: 500 })
  }
}
