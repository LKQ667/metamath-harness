import test from 'node:test'
import assert from 'node:assert/strict'
import type { CredentialProvider } from '@deepseek-ai/dsh-credentials'
import { managedQoderCredentialRef, resolveManagedQoderPat } from '../src/dsh/credential.ts'
import { qoderCredentialRef } from '../src/dsh/credential-contract.ts'

function provider(value: string | undefined, source = 'file'): CredentialProvider {
  return {
    resolve: async (ref: string) => {
      assert.equal(ref, qoderCredentialRef)
      return value === undefined ? undefined : { value, source }
    },
  } as unknown as CredentialProvider
}

test('managed Qoder credential uses its fixed DSH reference and trims the stored PAT', async () => {
  assert.equal(managedQoderCredentialRef, 'QODER_MANAGED_CREDENTIAL')
  assert.equal(await resolveManagedQoderPat(provider('  personal-token  ')), 'personal-token')
})

test('managed Qoder credential treats missing and ambient environment sources as unconfigured', async () => {
  assert.equal(await resolveManagedQoderPat(provider(undefined)), '')
  for (const source of ['env', 'project-env', 'user-env']) {
    assert.equal(await resolveManagedQoderPat(provider('must-not-authorize', source)), '')
  }
})

test('managed Qoder credential accepts provider-managed source names', async () => {
  assert.equal(await resolveManagedQoderPat(provider('stored', 'memory')), 'stored')
  assert.equal(await resolveManagedQoderPat(provider('stored', 'vault')), 'stored')
})
