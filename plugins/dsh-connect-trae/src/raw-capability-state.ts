import type { TraeRawChatCapability } from './raw-capability.ts'

export interface TraeRawCapabilitySnapshot {
  capability?: TraeRawChatCapability
  checkedAtMs?: number
  fingerprint?: string
}

/** In-memory capability state; success/failure expires and config changes invalidate it. */
export class TraeRawCapabilityState {
  private snapshot: TraeRawCapabilitySnapshot = {}
  constructor(private readonly ttlMs = 30 * 60_000) {}

  current(fingerprint: string, now = Date.now()): TraeRawChatCapability | undefined {
    const value = this.snapshot
    if (value.capability === undefined || value.checkedAtMs === undefined || value.fingerprint !== fingerprint) return undefined
    return now - value.checkedAtMs <= this.ttlMs ? value.capability : undefined
  }

  record(fingerprint: string, capability: TraeRawChatCapability, now = Date.now()): void {
    this.snapshot = { fingerprint, capability, checkedAtMs: now }
  }

  inspect(): Readonly<TraeRawCapabilitySnapshot> {
    return { ...this.snapshot }
  }

  invalidate(): void {
    this.snapshot = {}
  }
}
