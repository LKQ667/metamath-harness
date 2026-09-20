/** Shared DSH host/browser contract for the one managed Qoder credential. */

export const qoderCredentialRef = 'QODER_MANAGED_CREDENTIAL'

/** DSH's local provider uses `env` and `*-env` for ambient credential layers. */
export function isEnvironmentCredentialSource(source: string | undefined): boolean {
  return source === 'env' || source?.endsWith('-env') === true
}
