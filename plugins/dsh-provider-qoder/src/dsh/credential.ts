/** DSH host-side resolution of the one managed Qoder credential. */

import { credentialRef, type CredentialProvider } from '@deepseek-ai/dsh-credentials'
import { isEnvironmentCredentialSource, qoderCredentialRef } from './credential-contract.ts'

export const managedQoderCredentialRef = credentialRef(qoderCredentialRef)

/** Resolve only provider-managed storage; ambient environment layers are intentionally unsupported. */
export async function resolveManagedQoderPat(credentials: CredentialProvider): Promise<string> {
  const hit = await credentials.resolve(managedQoderCredentialRef)
  if (hit === undefined || isEnvironmentCredentialSource(hit.source)) return ''
  return hit.value.trim()
}
