import type { TraeCredential, TraeRefreshOutcome } from './auth.ts'

const CLIENT_ID_BY_EDITION: Partial<Record<TraeCredential['edition'], string>> = {
  cn: 'ono9krqynydwx5',
  solo: 'ono9krqynydwx5',
}

function normalizeHost(host: string): string {
  const value = host.trim()
  if (value === '') throw new Error('Trae refresh host is missing')
  return value.replace(/\/$/, '')
}

/** Refresh only editions whose client contract is currently evidenced. */
export async function refreshTraeCredential(credential: TraeCredential, signal?: AbortSignal): Promise<TraeRefreshOutcome> {
  const clientId = CLIENT_ID_BY_EDITION[credential.edition]
  if (clientId === undefined) throw new Error(`Trae ${credential.edition} refresh contract is not verified`)
  if (credential.refreshToken === undefined) throw new Error('Trae refresh token is missing')
  const response = await fetch(`${normalizeHost(credential.host)}/cloudide/api/v3/trae/oauth/ExchangeToken`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ClientID: clientId, RefreshToken: credential.refreshToken, ClientSecret: '-', UserID: credential.userId }),
    signal: signal ?? AbortSignal.timeout(30_000),
  })
  if (!response.ok) throw new Error(`Trae token refresh failed (http ${response.status})`)
  const payload = await response.json() as { Result?: Record<string, unknown> }
  const result = payload.Result
  const accessToken = typeof result?.['Token'] === 'string' ? result['Token'] : ''
  if (accessToken === '') throw new Error('Trae token refresh returned no token')
  const expiry = result?.['TokenExpireAt']
  const expiresAtMs = typeof expiry === 'number' ? expiry : typeof expiry === 'string' ? Date.parse(expiry) : Number.NaN
  if (!Number.isFinite(expiresAtMs)) throw new Error('Trae token refresh returned an invalid expiry')
  const refreshToken = typeof result?.['RefreshToken'] === 'string' && result['RefreshToken'] !== '' ? result['RefreshToken'] : undefined
  return { accessToken, ...refreshToken === undefined ? {} : { refreshToken }, expiresAtMs }
}
