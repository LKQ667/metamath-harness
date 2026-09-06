import { createHash } from 'node:crypto'
import type { TraeIdentity } from './identity.ts'
import type { TraeRawChatRuntimeConfig } from './raw-runtime-config.ts'

/** Stable non-secret fingerprint for capability-cache invalidation. */
export function rawCapabilityFingerprint(input: {
  endpoint: string
  edition: string
  identity: Pick<TraeIdentity, 'appVersion' | 'buildVersion'>
  runtime: TraeRawChatRuntimeConfig
}): string {
  const stable = JSON.stringify({
    endpoint: input.endpoint,
    edition: input.edition,
    appVersion: input.identity.appVersion ?? '',
    buildVersion: input.identity.buildVersion ?? '',
    runtime: input.runtime,
  })
  return createHash('sha256').update(stable).digest('hex')
}
