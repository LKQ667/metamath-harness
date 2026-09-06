import type { TraeChatResult, TraeUpstreamClient } from './upstream.ts'

export interface TraeFallbackUpstreamOptions {
  primary: TraeUpstreamClient
  fallback: TraeUpstreamClient
  onFallback?: (result: Extract<TraeChatResult, { ok: false }>) => void
}

/**
 * Optional primary route first, native SOLO tool-call route second. Fallback is intentionally narrow:
 * only definitive pre-stream schema/route incompatibilities may retry the same
 * user request. Authentication, credit, rate, cancellation, transport/server
 * failures, and every successful Response are never replayed.
 */
export class TraeFallbackUpstreamClient implements TraeUpstreamClient {
  constructor(private readonly options: TraeFallbackUpstreamOptions) {}

  async chatStream(bodyJson: string, signal?: AbortSignal): Promise<TraeChatResult> {
    const primary = await this.options.primary.chatStream(bodyJson, signal)
    if (primary.ok) return primary
    if (!this.canFallback(primary, signal)) return primary
    this.options.onFallback?.(primary)
    return this.options.fallback.chatStream(bodyJson, signal)
  }

  private canFallback(result: Extract<TraeChatResult, { ok: false }>, signal?: AbortSignal): boolean {
    if (signal?.aborted === true) return false
    if (result.kind === 'authentication' || result.kind === 'hard_credit' || result.kind === 'soft_rate') return false
    return result.status === 400 || result.status === 404 || result.status === 415 || result.kind === 'unconfigured'
  }
}
