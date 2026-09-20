/** Fetch and normalize the model catalog exposed to a Qoder subscriber. */

import type { CosyCredentials } from './wire/cosy.ts'
import { buildAuthHeaders } from './wire/cosy.ts'
import { getQoderModelListUrl, type QoderRegion } from './endpoints.ts'
import { QoderLlmError, qoderHttpError, qoderRequestId } from '../errors.ts'
import {
  redactLogPayload,
  redactLogValue,
  type QoderLogger,
} from './logging.ts'
import { normalizeQoderModels, type QoderCatalogModel } from '../catalog.ts'
import {
  defaultMaxErrorBytes,
  defaultMaxJsonBytes,
  defaultMetadataTimeoutMs,
  readLimitedText,
  withDeadline,
} from './request.ts'

export interface FetchQoderModelsOptions {
  fetch?: typeof fetch
  signal?: AbortSignal
  region?: QoderRegion
  logger?: QoderLogger
  timeoutMs?: number
}

export async function fetchQoderModels(
  credentials: CosyCredentials,
  options: FetchQoderModelsOptions = {},
): Promise<QoderCatalogModel[]> {
  const url = getQoderModelListUrl(options.region)
  const fetchImpl = options.fetch ?? globalThis.fetch
  const startedAt = performance.now()
  const deadline = withDeadline(options.signal, options.timeoutMs ?? defaultMetadataTimeoutMs)
  options.logger?.debug?.('[Qoder Models] Requesting model catalog', { url })
  try {
    const response = await fetchImpl(url, {
      method: 'GET',
      headers: { accept: 'application/json', ...buildAuthHeaders(null, url, credentials) },
      signal: deadline.signal,
    })
    options.logger?.debug?.('[Qoder Models] Catalog request completed', {
      url,
      status: response.status,
      durationMs: Math.round(performance.now() - startedAt),
      ...qoderRequestId(response.headers) === undefined ? {} : { requestId: qoderRequestId(response.headers) },
    })
    const text = await readLimitedText(
      response,
      response.ok ? defaultMaxJsonBytes : defaultMaxErrorBytes,
      'Qoder model discovery response',
    )
    if (!response.ok) {
      options.logger?.error?.('[Qoder Models] Catalog request failed', redactLogPayload(text))
      throw qoderHttpError(`Qoder model discovery failed with HTTP status ${response.status}.`, response)
    }
    let payload: unknown
    try {
      payload = JSON.parse(text)
    } catch {
      throw new QoderLlmError('Qoder model discovery returned invalid JSON.', 'MALFORMED_RESPONSE')
    }
    const models = normalizeQoderModels(payload, conflict => {
      options.logger?.warn?.('[Qoder Models] Conflicting catalog defaults; using fallback', { conflict })
    })
    if (models.length === 0) throw new QoderLlmError('Qoder model discovery returned no enabled models.', 'EMPTY_RESPONSE')
    return models
  } catch (error) {
    if (error instanceof QoderLlmError) throw error
    if (options.signal?.aborted) throw new QoderLlmError('Qoder model discovery was aborted.', 'ABORTED')
    if (deadline.timeoutSignal.aborted) throw new QoderLlmError('Qoder model discovery timed out.', 'TIMEOUT')
    options.logger?.error?.('[Qoder Models] Catalog network request failed', redactLogValue(error))
    throw new QoderLlmError('Qoder model discovery network request failed.', 'TRANSPORT', { cause: error })
  }
}
