import { describe, expect, it } from 'vitest'
import { rawCapabilityFingerprint } from '../src/raw-fingerprint.ts'

const base = {
  endpoint: 'https://host/api/ide/v2/llm_raw_chat', edition: 'cn',
  identity: { appVersion: '3.3.83', buildVersion: '20260730' },
  runtime: { configName: 'qwen', modelName: 'qwen', nativeFunctionCall: true },
}

describe('Raw Chat capability fingerprint', () => {
  it('is stable and contains no readable endpoint/model data', () => {
    const a = rawCapabilityFingerprint(base)
    const b = rawCapabilityFingerprint(structuredClone(base))
    expect(a).toBe(b)
    expect(a).toMatch(/^[a-f0-9]{64}$/)
    expect(a).not.toContain('qwen')
    expect(a).not.toContain('host')
  })

  it('changes with endpoint, version, or runtime config', () => {
    const original = rawCapabilityFingerprint(base)
    expect(rawCapabilityFingerprint({ ...base, endpoint: 'https://other' })).not.toBe(original)
    expect(rawCapabilityFingerprint({ ...base, identity: { ...base.identity, appVersion: '3.3.84' } })).not.toBe(original)
    expect(rawCapabilityFingerprint({ ...base, runtime: { ...base.runtime, nativeFunctionCall: false } })).not.toBe(original)
  })
})
