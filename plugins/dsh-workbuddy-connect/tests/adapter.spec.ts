import { describe, expect, it } from 'vitest'
import { createWorkBuddyAdapter } from '../src/adapter.ts'
import { WorkBuddyCatalog } from '../src/catalog.ts'
import { WORKBUDDY_PROVIDER } from '../src/adapter.ts'
import type { WorkBuddyCredentialStore } from '../src/auth.ts'
import type { WorkBuddyShim } from '../src/shim.ts'

/** The pi-ai collection built by an adapter exposes the exact model descriptor it consumes. */
interface AdapterSnapshot {
  models: {
    getModel(provider: string, model: string): { compat?: { maxTokensField?: string } } | undefined
  }
}

describe('WorkBuddy adapter model descriptors', () => {
  it('uses WorkBuddy\'s max_tokens output-cap field', () => {
    const catalog = new WorkBuddyCatalog([{
      id: 'model', name: 'Model', contextWindow: 1_000, maxTokens: 128_000,
      supportsImages: false, billing: { free: false },
    }])
    const { adapter } = createWorkBuddyAdapter({
      catalog,
      store: {} as WorkBuddyCredentialStore,
      shim: {
        ready: Promise.resolve(),
        baseUrl: () => 'http://127.0.0.1:1',
        token: () => 'test-token',
        close: async () => {},
      } as WorkBuddyShim,
    })

    // `current()` is private in the adapter's public API, but this is the
    // descriptor seam pi-ai reads before it serializes a request.
    const snapshot = (adapter as unknown as { current(): AdapterSnapshot }).current()
    expect(snapshot.models.getModel(WORKBUDDY_PROVIDER, 'model')?.compat?.maxTokensField).toBe('max_tokens')
  })
})
