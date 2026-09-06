export type TraeUpstreamErrorKind =
  | 'authentication'
  | 'hard_credit'
  | 'soft_rate'
  | 'not_found'
  | 'server'
  | 'client'
  | 'unconfigured'

export type TraeChatResult =
  | { ok: true; response: Response }
  | { ok: false; status: number; kind: TraeUpstreamErrorKind; message: string }

export interface TraeUpstreamClient {
  chatStream(bodyJson: string, signal?: AbortSignal): Promise<TraeChatResult>
}

/**
 * Safe first-stage upstream. Real Trae traffic stays disabled until one
 * edition-specific endpoint and wire codec are verified with fixtures.
 */
export class UnconfiguredTraeUpstreamClient implements TraeUpstreamClient {
  async chatStream(_bodyJson: string, _signal?: AbortSignal): Promise<TraeChatResult> {
    return {
      ok: false,
      status: 503,
      kind: 'unconfigured',
      message: 'Trae upstream protocol is not configured; complete offline protocol verification first',
    }
  }
}
