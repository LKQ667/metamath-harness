/**
 * Browser caller for the Qoder settings RPC.
 *
 * Requests go to Connection's shared `/api` channel, which the connection
 * plugin mounts itself and guards with its Host/Origin fence and browser
 * authentication; the caller only has to carry the session cookie.
 */

import {
  isQoderRpcErrorCode,
  qoderRpcPath,
  type QoderRpcEndpoint,
  type QoderRpcErrorCode,
  type QoderRpcResult,
} from '../dsh/rpc-channel.ts'

interface QoderRpcEnvelope {
  ok?: unknown
  value?: unknown
  error?: unknown
}

export interface QoderRpcTransport {
  /** Transport override for tests; defaults to the page's global fetch. */
  fetch?: typeof globalThis.fetch
}

export interface QoderRpcCaller {
  call<T>(endpoint: QoderRpcEndpoint, payload: unknown, signal?: AbortSignal): Promise<QoderRpcResult<T>>
}

/**
 * Create the caller used by the account card and the model catalog.
 *
 * Failures are returned rather than thrown so the cards keep their existing
 * "result or undefined" handling: a transport status becomes a transport
 * failure message, and an endpoint failure keeps the provider's own message.
 */
export function createQoderRpcCaller(transport: QoderRpcTransport = {}): QoderRpcCaller {
  const send = transport.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init))
  return {
    async call<T>(endpoint: QoderRpcEndpoint, payload: unknown, signal?: AbortSignal): Promise<QoderRpcResult<T>> {
      const path = qoderRpcPath(endpoint)
      try {
        const response = await send(path, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload ?? {}),
          ...signal === undefined ? {} : { signal },
        })
        if (!response.ok) {
          const code: QoderRpcErrorCode = signal?.aborted ? 'ABORTED' : 'UPSTREAM_ERROR'
          return {
            ok: false,
            error: {
              code,
              message: `transport failure for ${path}: HTTP ${response.status}`,
            },
          }
        }
        const envelope = await response.json() as QoderRpcEnvelope
        if (envelope?.ok === true) return { ok: true, value: envelope.value as T }

        const rawError = envelope?.error
        let code: QoderRpcErrorCode = 'INTERNAL'
        let message = 'RPC returned error'
        let details: object | undefined

        if (typeof rawError === 'string') {
          message = rawError
        } else if (typeof rawError === 'object' && rawError !== null) {
          const errObj = rawError as { code?: unknown; message?: unknown; details?: unknown }
          if (isQoderRpcErrorCode(errObj.code)) code = errObj.code
          if (typeof errObj.message === 'string') message = errObj.message
          if (typeof errObj.details === 'object' && errObj.details !== null) details = errObj.details
        }
        if (code === 'INTERNAL' && signal?.aborted) code = 'ABORTED'

        return {
          ok: false,
          error: {
            code,
            message,
            ...details === undefined ? {} : { details },
          },
        }
      } catch (error) {
        const isAbort = signal?.aborted || (error instanceof Error && error.name === 'AbortError')
        return {
          ok: false,
          error: {
            code: isAbort ? 'ABORTED' : 'INTERNAL',
            message: error instanceof Error ? error.message : String(error),
          },
        }
      }
    },
  }
}
