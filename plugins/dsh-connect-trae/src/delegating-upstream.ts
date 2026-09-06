import type { TraeChatResult, TraeUpstreamClient } from './upstream.ts'

/** Stable shim dependency whose delegate can be replaced after async setup. */
export class TraeDelegatingUpstreamClient implements TraeUpstreamClient {
  constructor(private delegate: TraeUpstreamClient) {}

  replace(delegate: TraeUpstreamClient): void { this.delegate = delegate }

  chatStream(bodyJson: string, signal?: AbortSignal): Promise<TraeChatResult> {
    const bound = this.delegate
    return bound.chatStream(bodyJson, signal)
  }
}
