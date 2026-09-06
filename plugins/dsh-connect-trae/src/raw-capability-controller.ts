import { probeTraeRawChatCapability, type TraeRawChatCapability } from './raw-capability.ts'
import { TraeRawCapabilityState } from './raw-capability-state.ts'
import type { TraeUpstreamClient } from './upstream.ts'

export interface TraeRawCapabilityControllerOptions {
  client: TraeUpstreamClient
  state?: TraeRawCapabilityState
  enabled?: boolean
}

/** Explicitly-triggered, single-flight Raw Chat capability checks. */
export class TraeRawCapabilityController {
  private readonly state: TraeRawCapabilityState
  private enabled: boolean
  private inflight: Promise<TraeRawChatCapability> | undefined

  constructor(private readonly options: TraeRawCapabilityControllerOptions) {
    this.state = options.state ?? new TraeRawCapabilityState()
    this.enabled = options.enabled ?? false
  }

  current(fingerprint: string): TraeRawChatCapability | undefined {
    return this.enabled ? this.state.current(fingerprint) : undefined
  }

  setEnabled(enabled: boolean): void {
    if (this.enabled !== enabled) this.state.invalidate()
    this.enabled = enabled
  }

  inspect() { return this.state.inspect() }

  isEnabled(): boolean { return this.enabled }

  invalidate(): void { this.state.invalidate() }

  probe(fingerprint: string, signal?: AbortSignal): Promise<TraeRawChatCapability> {
    if (!this.enabled) return Promise.resolve({ available: false, reason: 'protocol', status: 0 })
    const cached = this.state.current(fingerprint)
    if (cached !== undefined) return Promise.resolve(cached)
    this.inflight ??= probeTraeRawChatCapability(this.options.client, signal)
      .then(result => { this.state.record(fingerprint, result); return result })
      .finally(() => { this.inflight = undefined })
    return this.inflight
  }
}
