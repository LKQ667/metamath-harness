import { describe, expect, it } from 'vitest'
import { TraeRawCapabilityState } from '../src/raw-capability-state.ts'

describe('TraeRawCapabilityState', () => {
  it('reuses a fresh result only for the same configuration fingerprint', () => {
    const state = new TraeRawCapabilityState(1000)
    state.record('a', { available: true, contentType: 'text/event-stream' }, 100)
    expect(state.current('a', 1100)).toEqual({ available: true, contentType: 'text/event-stream' })
    expect(state.current('a', 1101)).toBeUndefined()
    expect(state.current('b', 200)).toBeUndefined()
  })

  it('invalidates successes and failures explicitly', () => {
    const state = new TraeRawCapabilityState()
    state.record('a', { available: false, reason: 'protocol', status: 400 }, 100)
    expect(state.current('a', 101)).toEqual({ available: false, reason: 'protocol', status: 400 })
    state.invalidate()
    expect(state.current('a', 101)).toBeUndefined()
  })
})
