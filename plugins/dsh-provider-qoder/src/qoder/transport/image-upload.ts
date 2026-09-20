/**
 * Center-hosted image upload pipeline for Qoder multimodal input.
 *
 * Qoder does not carry raster bytes inside a model request. It publishes each
 * request image to the center service once, then references the returned
 * durable URL. This module owns that exchange: deduplication, single-flight
 * sharing, bounded caching, and the degradation contract that keeps a model
 * request alive when publication fails.
 *
 * @module dsh-provider-qoder/qoder/transport/image-upload
 */

import crypto from 'node:crypto'
import type { RequestImageAttachment } from '@deepseek-ai/dsh-attachment'
import { QoderLlmError } from '../errors.ts'
import { getQoderImageUploadUrl, type QoderRegion } from './endpoints.ts'
import { redactLogValue, type QoderLogger } from './logging.ts'
import { defaultMaxJsonBytes, readLimitedText, SingleFlight } from './request.ts'
import { buildAuthHeaders, type CosyCredentials } from './wire/cosy.ts'

/** Upstream deadline for one image publication attempt. */
export const defaultImageUploadTimeoutMs = 30_000
/** Bounded number of remembered image URLs, matching the Qoder client. */
export const defaultImageUrlCacheCapacity = 512
/**
 * Conservative lifetime for a remembered image URL.
 *
 * Whether the center service returns a permanently addressable object or a
 * pre-signed URL is not established. Remembering a pre-signed URL forever
 * would replay expiry failures for the rest of a long session with no way to
 * recover, so entries expire and are republished instead.
 */
export const defaultImageUrlCacheTtlMs = 30 * 60 * 1000
/** Concurrent publications allowed while preparing one model request. */
export const defaultImageUploadConcurrency = 4

const mediaTypeExtensions: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
}

export interface QoderImageUploaderOptions {
  fetch?: typeof fetch
  region?: QoderRegion
  logger?: QoderLogger
  timeoutMs?: number
  cacheTtlMs?: number
  cacheCapacity?: number
  maxConcurrency?: number
  /** Re-resolve credentials after the center service rejects the current ones. */
  refreshCredentials?: (signal?: AbortSignal) => Promise<CosyCredentials>
  now?: () => number
}

interface CacheEntry {
  url: string
  expiresAt: number
}

export interface QoderMultipartBody {
  body: Buffer
  boundary: string
}

function aborted(): QoderLlmError {
  return new QoderLlmError('Qoder image upload was aborted.', 'ABORTED')
}

/** Encode one image as a single-field multipart payload using the Qoder boundary shape. */
export function buildQoderImageMultipart(
  data: Uint8Array,
  mediaType: string,
  boundaryId: string = crypto.randomUUID(),
): QoderMultipartBody {
  const boundary = `----qodercli-${boundaryId}`
  const extension = mediaTypeExtensions[mediaType] ?? 'png'
  const header = Buffer.from(
    `--${boundary}\r\n`
    + `Content-Disposition: form-data; name="file"; filename="image.${extension}"\r\n`
    + `Content-Type: ${mediaType}\r\n\r\n`,
    'utf8',
  )
  const footer = Buffer.from(`\r\n--${boundary}--\r\n`, 'utf8')
  return { body: Buffer.concat([header, Buffer.from(data), footer]), boundary }
}

/**
 * Extract the durable object URL from a center upload response.
 *
 * @param payload - parsed response body.
 * @returns the first usable absolute URL, or undefined when none is present.
 */
export function readQoderImageUrl(payload: unknown): string | undefined {
  if (payload === null || typeof payload !== 'object') return undefined
  const root = payload as Record<string, unknown>
  const result = root.result as Record<string, unknown> | undefined
  const data = root.data as Record<string, unknown> | undefined
  const candidates = [
    root.url,
    result?.url,
    result?.oss_url,
    data?.url,
    data?.oss_url,
  ]
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue
    const trimmed = candidate.trim()
    if (trimmed.length === 0) continue
    if (!URL.canParse(trimmed)) continue
    return trimmed
  }
  return undefined
}

function dataUrl(image: Pick<RequestImageAttachment, 'data' | 'mediaType'>): string {
  return `data:${image.mediaType};base64,${Buffer.from(image.data).toString('base64')}`
}

/**
 * Publishes request images to the Qoder center service and remembers the result.
 *
 * Publication never fails a model request: any upstream problem degrades to an
 * inline data URL so the turn proceeds with the same content it would have
 * carried before the pipeline existed.
 */
export class QoderImageUploader {
  private readonly cache = new Map<string, CacheEntry>()
  private readonly flights = new SingleFlight<string>()
  private readonly fetchImpl: typeof fetch
  private readonly region: QoderRegion
  private readonly logger?: QoderLogger
  private readonly timeoutMs: number
  private readonly cacheTtlMs: number
  private readonly cacheCapacity: number
  private readonly maxConcurrency: number
  private readonly refreshCredentials?: (signal?: AbortSignal) => Promise<CosyCredentials>
  private readonly now: () => number
  private active = 0
  private readonly queue: Array<() => void> = []

  constructor(options: QoderImageUploaderOptions = {}) {
    this.fetchImpl = options.fetch ?? globalThis.fetch
    this.region = options.region ?? 'global'
    this.logger = options.logger
    this.timeoutMs = options.timeoutMs ?? defaultImageUploadTimeoutMs
    this.cacheTtlMs = options.cacheTtlMs ?? defaultImageUrlCacheTtlMs
    this.cacheCapacity = options.cacheCapacity ?? defaultImageUrlCacheCapacity
    this.maxConcurrency = options.maxConcurrency ?? defaultImageUploadConcurrency
    this.refreshCredentials = options.refreshCredentials
    this.now = options.now ?? Date.now
  }

  /**
   * Resolve the wire URL for one request image.
   *
   * @param image - request-encoded image produced by the DSH attachment store.
   * @param credentials - credentials authorizing the center exchange.
   * @param signal - optional caller cancellation.
   * @returns a center object URL, or an inline data URL when publication fails.
   * @throws QoderLlmError with code `ABORTED` only when the caller cancels.
   */
  async resolveImageUrl(
    image: RequestImageAttachment,
    credentials: CosyCredentials,
    signal?: AbortSignal,
  ): Promise<string> {
    if (signal?.aborted) throw aborted()

    const key = this.cacheKey(image, credentials)
    const cached = this.cache.get(key)
    if (cached !== undefined) {
      if (cached.expiresAt > this.now()) {
        // Refresh recency so the bounded cache evicts genuinely cold entries.
        this.cache.delete(key)
        this.cache.set(key, cached)
        this.logger?.debug?.('[image-upload] cache hit', {
          url: cached.url,
          region: this.region,
          mediaType: image.mediaType,
          bytes: image.data.byteLength,
        })
        return cached.url
      }
      this.cache.delete(key)
    }

    return this.flights.run(
      key,
      signal,
      async (sharedSignal) => {
        const url = await this.publish(image, credentials, sharedSignal)
        if (url !== undefined) {
          this.remember(key, url)
          return url
        }
        return dataUrl(image)
      },
      aborted,
    )
  }

  /**
   * Derive the deduplication identity for one request image.
   *
   * `variantId` is the attachment store's deterministic cache and upload index
   * over the attachment, the request policy, and the encoder parameters, so it
   * identifies these exact bytes without rehashing them. Region and subscriber
   * are included because a center object is never shared across either.
   */
  private cacheKey(image: RequestImageAttachment, credentials: CosyCredentials): string {
    const hash = crypto.createHash('sha256')
    hash.update(getQoderImageUploadUrl(this.region))
    hash.update('\0')
    hash.update(credentials.userID)
    hash.update('\0')
    hash.update(image.mediaType)
    hash.update('\0')
    const variantId = typeof image.variantId === 'string' ? image.variantId : ''
    if (variantId.length > 0) {
      hash.update(variantId)
    } else {
      hash.update(crypto.createHash('sha256').update(Buffer.from(image.data)).digest('hex'))
    }
    return hash.digest('hex')
  }

  private remember(key: string, url: string): void {
    this.cache.delete(key)
    this.cache.set(key, { url, expiresAt: this.now() + this.cacheTtlMs })
    while (this.cache.size > this.cacheCapacity) {
      const oldest = this.cache.keys().next()
      if (oldest.done === true) break
      this.cache.delete(oldest.value)
    }
  }

  private async withSlot<T>(signal: AbortSignal, operation: () => Promise<T>): Promise<T> {
    if (signal.aborted) throw aborted()
    if (this.active >= this.maxConcurrency) {
      this.logger?.debug?.('[image-upload] queued', {
        region: this.region,
        active: this.active,
        queued: this.queue.length + 1,
      })
      await new Promise<void>((resolve, reject) => {
        const onAbort = (): void => {
          const index = this.queue.indexOf(release)
          if (index !== -1) this.queue.splice(index, 1)
          reject(aborted())
        }
        const release = (): void => {
          signal.removeEventListener('abort', onAbort)
          resolve()
        }
        signal.addEventListener('abort', onAbort, { once: true })
        this.queue.push(release)
      })
    } else {
      this.active++
    }
    try {
      if (signal.aborted) throw aborted()
      return await operation()
    } finally {
      const next = this.queue.shift()
      if (next !== undefined) next()
      else this.active--
    }
  }

  /** Attempt publication, returning undefined when the request must degrade. */
  private async publish(
    image: RequestImageAttachment,
    credentials: CosyCredentials,
    signal: AbortSignal,
  ): Promise<string | undefined> {
    return this.withSlot(signal, async () => {
      const first = await this.attempt(image, credentials, signal)
      if (first.url !== undefined) return first.url
      if (!first.retryable || this.refreshCredentials === undefined) {
        this.warnDegraded(first.reason)
        return undefined
      }

      let refreshed: CosyCredentials
      this.logger?.debug?.('[image-upload] refreshing credentials before retry', {
        region: this.region,
        reason: first.reason,
      })
      try {
        refreshed = await this.refreshCredentials(signal)
      } catch (error) {
        if (signal.aborted) throw aborted()
        this.warnDegraded('credential refresh failed', error)
        return undefined
      }
      const second = await this.attempt(image, refreshed, signal)
      if (second.url !== undefined) return second.url
      this.warnDegraded(second.reason)
      return undefined
    })
  }

  private warnDegraded(reason: string, cause?: unknown): void {
    this.logger?.warn?.(
      '[image-upload] upload failed, keeping base64 image',
      { region: this.region, reason },
      ...cause === undefined ? [] : [redactLogValue(cause)],
    )
  }

  private async attempt(
    image: RequestImageAttachment,
    credentials: CosyCredentials,
    signal: AbortSignal,
  ): Promise<{ url?: string; retryable: boolean; reason: string }> {
    const requestId = crypto.randomUUID()
    const url = getQoderImageUploadUrl(this.region, requestId)
    const multipart = buildQoderImageMultipart(image.data, image.mediaType)
    // The Qoder client signs the body *length*, not the body: prepareRequest
    // receives String(body.length). Signing raw multipart bytes would corrupt
    // them, because the signature input is assembled as text.
    const signedBody = Buffer.from(String(multipart.body.length), 'utf8')
    const timeout = AbortSignal.timeout(this.timeoutMs)
    const requestSignal = AbortSignal.any([signal, timeout])
    const startedAt = this.now()
    const details = {
      requestId,
      region: this.region,
      mediaType: image.mediaType,
      bytes: image.data.byteLength,
      timeoutMs: this.timeoutMs,
    }
    this.logger?.debug?.('[image-upload] started', details)

    try {
      const response = await this.fetchImpl(url, {
        method: 'PUT',
        headers: {
          ...buildAuthHeaders(signedBody, url, credentials),
          'AI-CLIENT-TIMESTAMP': String(Math.floor(this.now() / 1000)),
          'Content-Type': `multipart/form-data; boundary=${multipart.boundary}`,
          'Content-Length': String(multipart.body.length),
          'accept': 'application/json',
        },
        body: new Uint8Array(multipart.body),
        signal: requestSignal,
      })
      this.logger?.debug?.('[image-upload] response received', {
        requestId,
        status: response.status,
        elapsedMs: this.now() - startedAt,
      })
      const text = await readLimitedText(response, defaultMaxJsonBytes, 'Qoder image upload response')
      if (!response.ok) {
        return {
          retryable: response.status === 401 || response.status === 403,
          reason: `HTTP ${response.status}`,
        }
      }
      let payload: unknown
      try {
        payload = JSON.parse(text)
      } catch {
        return { retryable: false, reason: 'invalid JSON response' }
      }
      const resolved = readQoderImageUrl(payload)
      if (resolved === undefined) return { retryable: false, reason: 'response carried no image URL' }
      this.logger?.debug?.('[image-upload] succeeded', {
        ...details,
        status: response.status,
        elapsedMs: this.now() - startedAt,
        url: resolved
      })
      return { url: resolved, retryable: false, reason: '' }
    } catch (error) {
      const failureDetails = { requestId, region: this.region, elapsedMs: this.now() - startedAt }
      if (signal.aborted) {
        this.logger?.debug?.('[image-upload] aborted', failureDetails)
        throw aborted()
      }
      if (timeout.aborted) {
        this.logger?.debug?.('[image-upload] timed out', failureDetails)
        return { retryable: false, reason: 'upload timed out' }
      }
      this.logger?.debug?.('[image-upload] network failure', failureDetails, redactLogValue(error))
      return { retryable: false, reason: 'network failure' }
    }
  }
}
