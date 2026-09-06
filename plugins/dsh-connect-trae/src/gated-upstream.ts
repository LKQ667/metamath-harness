import type { TraeRawChatCapability } from './raw-capability.ts'
import { TraeFallbackUpstreamClient } from './fallback-upstream.ts'
import type { TraeChatResult, TraeUpstreamClient } from './upstream.ts'

export interface TraeGatedUpstreamOptions {
  raw: TraeUpstreamClient
  solo: TraeUpstreamClient
  capability(): TraeRawChatCapability | undefined
  onFallback?: (failure: Extract<TraeChatResult, { ok: false }>) => void
}

/** Select Raw Chat only after a successful capability probe; SOLO is the safe default. */
export class TraeGatedUpstreamClient implements TraeUpstreamClient {
  constructor(private readonly options: TraeGatedUpstreamOptions) {}

  chatStream(bodyJson: string, signal?: AbortSignal): Promise<TraeChatResult> {
    if (this.options.capability()?.available !== true) return this.options.solo.chatStream(bodyJson, signal)
    return new TraeFallbackUpstreamClient({
      primary: this.options.raw,
      fallback: this.options.solo,
      ...this.options.onFallback === undefined ? {} : { onFallback: this.options.onFallback },
    }).chatStream(bodyJson, signal)
  }
}
