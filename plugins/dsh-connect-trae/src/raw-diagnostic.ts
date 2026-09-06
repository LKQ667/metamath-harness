import type { TraeRawChatCapability } from './raw-capability.ts'

export type TraeRawDiagnosticState =
  | 'disabled'
  | 'unchecked'
  | 'available'
  | 'protocol-gated'
  | 'authentication'
  | 'credit'
  | 'rate'
  | 'transport'
  | 'server'

export interface TraeRawDiagnostic {
  state: TraeRawDiagnosticState
  checkedAtMs?: number
  status?: number
}

/** Project capability facts to a redacted, user-safe status. */
export function rawCapabilityDiagnostic(enabled: boolean, capability?: TraeRawChatCapability, checkedAtMs?: number): TraeRawDiagnostic {
  if (!enabled) return { state: 'disabled' }
  if (capability === undefined) return { state: 'unchecked' }
  if (capability.available) return { state: 'available', ...checkedAtMs === undefined ? {} : { checkedAtMs } }
  const state = capability.reason === 'protocol' ? 'protocol-gated' : capability.reason
  return { state, status: capability.status, ...checkedAtMs === undefined ? {} : { checkedAtMs } }
}
