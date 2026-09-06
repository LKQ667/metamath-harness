import type { TraeIdentity } from './identity.ts'
import { probeTraeRawChatCapability } from './raw-capability.ts'
import { TraeRawCapabilityController } from './raw-capability-controller.ts'
import { rawCapabilityFingerprint } from './raw-fingerprint.ts'
import { rawCapabilityDiagnostic, type TraeRawDiagnostic } from './raw-diagnostic.ts'
import { TraeGatedUpstreamClient } from './gated-upstream.ts'
import type { TraeRawChatRuntimeConfig } from './raw-runtime-config.ts'
import type { TraeUpstreamClient } from './upstream.ts'

export interface TraeRawGatewayOptions {
  raw: TraeUpstreamClient
  solo: TraeUpstreamClient
  endpoint: string
  edition: string
  identity: Pick<TraeIdentity, 'appVersion' | 'buildVersion'>
  runtime: TraeRawChatRuntimeConfig
  enabled?: boolean
}

export interface TraeRawGateway {
  upstream: TraeUpstreamClient
  probe(signal?: AbortSignal): ReturnType<typeof probeTraeRawChatCapability>
  diagnostic(): TraeRawDiagnostic
  invalidate(): void
}

/** Assemble the opt-in capability state and safe Raw→SOLO routing. */
export function createTraeRawGateway(options: TraeRawGatewayOptions): TraeRawGateway {
  const fingerprint = () => rawCapabilityFingerprint(options)
  const controller = new TraeRawCapabilityController({ client: options.raw, enabled: options.enabled ?? false })
  const upstream = new TraeGatedUpstreamClient({ raw: options.raw, solo: options.solo, capability: () => controller.current(fingerprint()) })
  return {
    upstream,
    probe: signal => controller.probe(fingerprint(), signal),
    diagnostic: () => {
      const snapshot = controller.inspect()
      return rawCapabilityDiagnostic(controller.isEnabled(), snapshot.capability, snapshot.checkedAtMs)
    },
    invalidate: () => controller.invalidate(),
  }
}
