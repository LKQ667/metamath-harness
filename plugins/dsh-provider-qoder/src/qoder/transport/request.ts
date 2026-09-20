/** Internal request lifecycle primitives for the Qoder transport. */

import { createHash } from 'node:crypto'
import { QoderLlmError, qoderHttpError, qoderRequestId } from '../errors.ts'
import { logParsedResponse, redactLogPayload, type QoderLogger } from './logging.ts'
import { defaultUserAgent, qoderClientType } from './wire/cosy.ts'

export const defaultMetadataTimeoutMs = 15_000
export const defaultResponseHeaderTimeoutMs = 60_000
export const defaultMaxJsonBytes = 2 * 1024 * 1024
export const defaultMaxErrorBytes = 16 * 1024
const metadataRetryBaseDelayMs = 200
const maxProviderRetryDelayMs = 10_000

export function opaqueCredentialKey(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

function retryableMetadataError(error: unknown): error is QoderLlmError {
  return error instanceof QoderLlmError
    && ['RATE_LIMIT', 'SERVER', 'TIMEOUT', 'TRANSPORT'].includes(error.code)
}

function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new DOMException('aborted', 'AbortError'))
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = (): void => {
      clearTimeout(timer)
      reject(new DOMException('aborted', 'AbortError'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
  })
}

export async function retryMetadataRead<T>(
  signal: AbortSignal,
  operation: () => Promise<T>,
): Promise<T> {
  try {
    return await operation()
  } catch (error) {
    if (!retryableMetadataError(error) || signal.aborted) throw error
    const providerDelay = error.failure.providerRetryAfterMs
    const delayMs = providerDelay === undefined
      ? metadataRetryBaseDelayMs + Math.floor(Math.random() * 41)
      : Math.min(providerDelay, maxProviderRetryDelayMs)
    await abortableDelay(delayMs, signal)
    return operation()
  }
}

export function withDeadline(
  signal: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; timeoutSignal: AbortSignal } {
  const timeoutSignal = AbortSignal.timeout(timeoutMs)
  return {
    timeoutSignal,
    signal: signal === undefined ? timeoutSignal : AbortSignal.any([signal, timeoutSignal]),
  }
}

export async function readLimitedText(
  response: Response,
  maxBytes: number,
  label: string,
): Promise<string> {
  const declaredLength = Number(response.headers.get('content-length'))
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    await response.body?.cancel().catch(() => undefined)
    throw new QoderLlmError(`${label} exceeded its response size limit.`, 'MALFORMED_RESPONSE')
  }
  if (!response.body) return ''

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let bytes = 0
  let text = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      bytes += value.byteLength
      if (bytes > maxBytes) {
        throw new QoderLlmError(`${label} exceeded its response size limit.`, 'MALFORMED_RESPONSE')
      }
      text += decoder.decode(value, { stream: true })
    }
    return text + decoder.decode()
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

interface Flight<T> {
  controller: AbortController
  promise: Promise<T>
  settled: boolean
  waiters: number
}

export class SingleFlight<T> {
  private readonly flights = new Map<string, Flight<T>>()

  run(
    key: string,
    signal: AbortSignal | undefined,
    start: (signal: AbortSignal) => Promise<T>,
    abortedError: () => Error,
  ): Promise<T> {
    if (signal?.aborted) return Promise.reject(abortedError())

    let flight = this.flights.get(key)
    if (flight === undefined || flight.controller.signal.aborted) {
      const controller = new AbortController()
      const created = {} as Flight<T>
      created.controller = controller
      created.settled = false
      created.waiters = 0
      created.promise = start(controller.signal).finally(() => {
        created.settled = true
        if (this.flights.get(key) === created) this.flights.delete(key)
      })
      flight = created
      this.flights.set(key, created)
    }

    flight.waiters++
    return new Promise<T>((resolve, reject) => {
      let finished = false
      const finish = (callback: () => void): void => {
        if (finished) return
        finished = true
        signal?.removeEventListener('abort', onAbort)
        flight.waiters--
        if (flight.waiters === 0 && !flight.settled) {
          if (this.flights.get(key) === flight) this.flights.delete(key)
          flight.controller.abort('all callers aborted')
        }
        callback()
      }
      const onAbort = (): void => finish(() => reject(abortedError()))
      signal?.addEventListener('abort', onAbort, { once: true })
      flight.promise.then(
        value => finish(() => resolve(value)),
        error => finish(() => reject(error)),
      )
    })
  }
}

export interface OpenApiJsonRequestOptions {
  url: string
  method?: 'GET' | 'POST'
  token?: string
  machineId?: string
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
  timeoutMs?: number
  logger?: QoderLogger
  operation: string
  logCategory?: string
  userAgent?: string
}

export async function openApiJsonRequest<T>(
  fetchImpl: typeof fetch,
  options: OpenApiJsonRequestOptions,
): Promise<T> {
  const method = options.method ?? (options.body !== undefined ? 'POST' : 'GET')
  const timeoutMs = options.timeoutMs ?? defaultMetadataTimeoutMs
  const timeoutSignal = AbortSignal.timeout(timeoutMs)
  const requestSignal = options.signal === undefined
    ? timeoutSignal
    : AbortSignal.any([options.signal, timeoutSignal])
  const startedAt = performance.now()

  options.logger?.debug?.(`[Qoder ${options.operation}] Requesting`, { url: options.url, method })

  try {
    const headers: Record<string, string> = {
      accept: 'application/json',
      'user-agent': options.userAgent ?? defaultUserAgent,
      'cosy-version': '1.0.1',
      'cosy-clienttype': qoderClientType,
      ...options.headers,
    }
    if (options.token) {
      headers.authorization = `Bearer ${options.token}`
    }
    if (options.machineId) {
      headers['Cosy-MachineToken'] = options.machineId
      headers['Cosy-MachineType'] = 'host'
    }
    let bodyText: string | undefined
    if (options.body !== undefined) {
      headers['content-type'] = 'application/json'
      bodyText = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
    }

    const response = await fetchImpl(options.url, {
      method,
      headers,
      body: bodyText,
      signal: requestSignal,
    })

    options.logger?.debug?.(`[Qoder ${options.operation}] Request completed`, {
      status: response.status,
      statusText: response.statusText,
      durationMs: Math.round(performance.now() - startedAt),
      ...qoderRequestId(response.headers) === undefined ? {} : { requestId: qoderRequestId(response.headers) },
    })

    const text = await readLimitedText(
      response,
      response.ok ? defaultMaxJsonBytes : defaultMaxErrorBytes,
      `Qoder ${options.operation} response`,
    )

    if (!response.ok) {
      options.logger?.error?.(`[Qoder ${options.operation}] Request failed`, redactLogPayload(text))
      throw qoderHttpError(
        `Failed to execute Qoder ${options.operation} with status ${response.status}.`,
        response,
      )
    }

    let data: unknown
    try {
      data = JSON.parse(text)
    } catch {
      options.logger?.error?.(`[Qoder ${options.operation}] Invalid JSON response`, redactLogPayload(text))
      throw new QoderLlmError(`Failed to parse Qoder ${options.operation} JSON response`, 'MALFORMED_RESPONSE')
    }

    if (options.logCategory) {
      logParsedResponse(options.logger, options.logCategory, data)
    }

    return data as T
  } catch (error: unknown) {
    if (error instanceof QoderLlmError) throw error
    if (options.signal?.aborted) {
      throw new QoderLlmError(`Qoder ${options.operation} request was aborted.`, 'ABORTED')
    }
    if (timeoutSignal.aborted) {
      throw new QoderLlmError(`Qoder ${options.operation} request timed out.`, 'TIMEOUT')
    }
    throw new QoderLlmError(`Qoder ${options.operation} network request failed.`, 'TRANSPORT', { cause: error })
  }
}
