import { describe, expect, it } from 'vitest'
import { rawCapabilityDiagnostic } from '../src/raw-diagnostic.ts'

describe('Raw Chat redacted diagnostics', () => {
  it('distinguishes disabled, unchecked and available', () => {
    expect(rawCapabilityDiagnostic(false)).toEqual({ state: 'disabled' })
    expect(rawCapabilityDiagnostic(true)).toEqual({ state: 'unchecked' })
    expect(rawCapabilityDiagnostic(true, { available: true, contentType: 'text/event-stream' }, 10)).toEqual({ state: 'available', checkedAtMs: 10 })
  })

  it('projects failures without retaining messages or credentials', () => {
    expect(rawCapabilityDiagnostic(true, { available: false, reason: 'protocol', status: 400 }, 10)).toEqual({ state: 'protocol-gated', status: 400, checkedAtMs: 10 })
    expect(rawCapabilityDiagnostic(true, { available: false, reason: 'authentication', status: 401 })).toEqual({ state: 'authentication', status: 401 })
    expect(rawCapabilityDiagnostic(true, { available: false, reason: 'credit', status: 402 })).toEqual({ state: 'credit', status: 402 })
  })
})
