/**
 * Web search transport client communicating with the Qoder center service.
 *
 * Dispatches query requests to the center-hosted `oneSearch` route using the
 * subscriber's COSY credentials, handling payload serialization, signing,
 * 401/403 credential refresh retry, and mapping to DSH WebSearchResult.
 *
 * @module dsh-provider-qoder/qoder/transport/search
 */

import { WebError, type WebSearchRequest, type WebSearchResult, type WebSearchSource } from '@deepseek-ai/dsh-web'
import { getQoderWebSearchUrl, type QoderRegion } from './endpoints.ts'
import { redactLogValue, type QoderLogger } from './logging.ts'
import { defaultMaxJsonBytes, readLimitedText } from './request.ts'
import { buildAuthHeaders, type CosyCredentials } from './wire/cosy.ts'
import { qoderEncodeBody } from './wire/encoding.ts'

export const defaultSearchTimeoutMs = 30_000

export interface QoderSearchClientOptions {
  fetch?: typeof fetch
  region?: QoderRegion
  logger?: QoderLogger
  timeoutMs?: number
  resolveCredentials: (signal?: AbortSignal) => Promise<CosyCredentials>
  refreshCredentials?: (signal?: AbortSignal) => Promise<CosyCredentials>
  now?: () => number
}

interface QoderSearchPageItem {
  title?: string
  link?: string
  snippet?: string
  publishedAt?: string
}

interface QoderSearchResponse {
  errorCode?: number
  errorMsg?: string
  requestId?: string
  pageItems?: QoderSearchPageItem[]
}

function searchAborted(signal?: AbortSignal, fallback?: unknown): WebError {
  return new WebError('Web search was cancelled.', 'WEB_ABORTED', {
    cause: signal?.aborted === true ? signal.reason : fallback,
  })
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export class QoderSearchClient {
  private readonly fetchImpl: typeof fetch
  private readonly region: QoderRegion
  private readonly logger?: QoderLogger
  private readonly timeoutMs: number
  private readonly resolveCredentials: (signal?: AbortSignal) => Promise<CosyCredentials>
  private readonly refreshCredentials?: (signal?: AbortSignal) => Promise<CosyCredentials>
  private readonly now: () => number

  constructor(options: QoderSearchClientOptions) {
    this.fetchImpl = options.fetch ?? globalThis.fetch
    this.region = options.region ?? 'global'
    this.logger = options.logger
    this.timeoutMs = options.timeoutMs ?? defaultSearchTimeoutMs
    this.resolveCredentials = options.resolveCredentials
    this.refreshCredentials = options.refreshCredentials
    this.now = options.now ?? Date.now
  }

  async search(request: WebSearchRequest, signal?: AbortSignal): Promise<WebSearchResult> {
    if (signal?.aborted) throw searchAborted(signal)

    let credentials = await this.resolveCredentials(signal)
    if (signal?.aborted) throw searchAborted(signal)

    const first = await this.attempt(request, credentials, signal)
    if (first.result !== undefined) return first.result

    if (first.retryable && this.refreshCredentials !== undefined) {
      this.logger?.debug?.('[web-search] refreshing credentials before retry', {
        region: this.region,
        reason: first.reason,
      })
      try {
        credentials = await this.refreshCredentials(signal)
      } catch (error) {
        if (signal?.aborted) throw searchAborted(signal, error)
        throw new WebError(`Qoder credential refresh failed: ${String(error)}`, 'WEB_PROVIDER_ERROR', { cause: error })
      }
      const second = await this.attempt(request, credentials, signal)
      if (second.result !== undefined) return second.result
      throw new WebError(`Qoder web search failed: ${second.reason}`, 'WEB_PROVIDER_ERROR')
    }

    throw new WebError(`Qoder web search failed: ${first.reason}`, 'WEB_PROVIDER_ERROR')
  }

  private async attempt(
    request: WebSearchRequest,
    credentials: CosyCredentials,
    signal?: AbortSignal,
  ): Promise<{ result?: WebSearchResult; retryable: boolean; reason: string }> {
    const url = getQoderWebSearchUrl(this.region)
    const innerPayload = {
      query: request.query,
      timeRange: 'NoLimit',
      contents: {
        mainText: false,
        markdownText: false,
        summary: false,
      },
    }
    const outerBody = JSON.stringify({
      payload: JSON.stringify(innerPayload),
      encodeVersion: '1',
    })
    const encodedBody = qoderEncodeBody(outerBody)

    const timeout = AbortSignal.timeout(this.timeoutMs)
    const requestSignal = signal !== undefined ? AbortSignal.any([signal, timeout]) : timeout
    const startedAt = this.now()

    this.logger?.debug?.('[web-search] started', {
      region: this.region,
      url,
      query: request.query,
    })

    let response: Response
    try {
      const authHeaders = buildAuthHeaders(encodedBody, url, credentials)
      response = await this.fetchImpl(url, {
        method: 'POST',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Accept-Encoding': 'identity',
        },
        body: encodedBody,
        signal: requestSignal,
      })
    } catch (error) {
      if (signal?.aborted) throw searchAborted(signal, error)
      if (timeout.aborted || isAbortError(error)) {
        return { retryable: false, reason: 'request timed out' }
      }
      this.logger?.warn?.('[web-search] network failure', { region: this.region }, redactLogValue(error))
      return { retryable: false, reason: `network failure: ${String(error)}` }
    }

    const elapsedMs = this.now() - startedAt
    this.logger?.debug?.('[web-search] response received', {
      status: response.status,
      elapsedMs,
    })

    if (!response.ok) {
      const isAuthError = response.status === 401 || response.status === 403
      return {
        retryable: isAuthError,
        reason: `HTTP ${response.status} ${response.statusText}`.trim(),
      }
    }

    let text: string
    try {
      text = await readLimitedText(response, defaultMaxJsonBytes, 'Qoder web search response')
    } catch (error) {
      if (signal?.aborted) throw searchAborted(signal, error)
      return { retryable: false, reason: `failed to read response body: ${String(error)}` }
    }

    let parsed: QoderSearchResponse
    try {
      parsed = JSON.parse(text) as QoderSearchResponse
    } catch (error) {
      return { retryable: false, reason: `invalid JSON response: ${String(error)}` }
    }

    if (parsed.errorCode != null && parsed.errorCode !== 0) {
      return {
        retryable: false,
        reason: `backend error code ${parsed.errorCode}: ${parsed.errorMsg ?? 'unknown'}`,
      }
    }

    const rawItems = parsed.pageItems ?? []
    const sources: WebSearchSource[] = []
    const seen = new Set<string>()

    for (const item of rawItems) {
      if (!item.link || item.link.trim().length === 0) continue
      const link = item.link.trim()
      if (seen.has(link)) continue
      seen.add(link)

      sources.push({
        url: link,
        ...item.title !== undefined && item.title.trim().length > 0 ? { title: item.title.trim() } : {},
        ...item.snippet !== undefined && item.snippet.trim().length > 0 ? { snippet: item.snippet.trim() } : {},
        ...item.publishedAt !== undefined && item.publishedAt.trim().length > 0 ? { publishedAt: item.publishedAt.trim() } : {},
      })
    }

    this.logger?.debug?.('[web-search] succeeded', {
      region: this.region,
      resultsCount: sources.length,
      elapsedMs,
    })

    return {
      result: {
        sources,
        truncated: false,
      },
      retryable: false,
      reason: '',
    }
  }
}
