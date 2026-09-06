import { describe, expect, it, vi } from 'vitest'
import { resolveTraeRawRuntime } from '../src/raw-resolver.ts'
import type { TraeCredentialStore } from '../src/auth.ts'

vi.mock('../src/identity.ts', () => ({ readTraeIdentity: vi.fn(async candidate => ({ edition: candidate.edition, machineId: 'm', deviceId: 'd', platform: 'darwin', appVersion: '1' })) }))
vi.mock('../src/model-cache.ts', () => ({ readTraeCachedModel: vi.fn(async () => ({ name: 'qwen', maxTokens: 32000, customConfig: { native_function_call: true, use_v2_process: true } })) }))

describe('Raw Chat runtime resolver', () => {
  it('uses current credential edition, desktop identity and safe cache', async () => {
    const store = {
      resolve: async () => ({ accessToken: 'secret', userId: 'u', host: 'https://host', expiresAtMs: 1, edition: 'cn', source: 'desktop' }),
      candidates: () => [{ edition: 'cn', path: '/safe/storage.json' }],
    } as unknown as TraeCredentialStore
    const result = await resolveTraeRawRuntime(store, 'qwen')
    expect(result.identity).toMatchObject({ edition: 'cn', appVersion: '1' })
    expect(result.runtime).toMatchObject({
      configName: 'qwen', modelName: 'qwen', maxTokens: 32000,
      nativeFunctionCall: true, useV2Process: true, passBackReasoning: true,
    })
  })
})
