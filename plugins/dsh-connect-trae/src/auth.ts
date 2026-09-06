import { readFile, rm, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { join } from 'node:path'
import { withFileLock, writeFileAtomic } from '@deepseek-ai/dsh-atomic-write'
import { resolveDshHome } from '@deepseek-ai/dsh-home-paths'
import { parseTraeStorageDocument } from './decrypt.ts'
import { traeStorageCandidates, type TraeEdition, type TraeStorageCandidate } from './paths.ts'

export interface TraeCredential {
  accessToken: string
  refreshToken?: string
  userId: string
  accountName?: string
  host: string
  expiresAtMs: number
  refreshExpiresAtMs?: number
  edition: TraeEdition
  source: 'desktop' | 'dsh'
}

export interface TraeRefreshOutcome {
  accessToken: string
  refreshToken?: string
  expiresAtMs: number
  refreshExpiresAtMs?: number
  host?: string
}

export interface TraeCredentialStoreOptions {
  storagePath?: string
  edition?: TraeEdition | 'auto'
  accountId?: string
  ownPath?: string
  refresh: (credential: TraeCredential) => Promise<TraeRefreshOutcome>
  refreshMarginMs?: number
}

export interface TraeAccountChoice {
  id: string
  accountName: string
  edition: TraeEdition
  source: 'desktop' | 'dsh'
  tokenExpiresAtMs: number
  selected: boolean
}

const OWN_VERSION = 1
export const TRAE_AUTH_FILENAME = '.trae-auth.json'

export function traeOwnAuthPath(): string {
  return join(resolveDshHome(), TRAE_AUTH_FILENAME)
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value !== '' ? value : undefined
}

function timeToMs(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value > 1e12 ? value : value * 1000
  if (typeof value !== 'string' || value.trim() === '') return undefined
  const numeric = Number(value)
  if (Number.isFinite(numeric) && numeric > 0) return numeric > 1e12 ? numeric : numeric * 1000
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

export function normalizeTraeCredential(raw: unknown, edition: TraeEdition, source: TraeCredential['source']): TraeCredential | undefined {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return undefined
  const value = raw as Record<string, unknown>
  const accessToken = optionalString(value['token']) ?? optionalString(value['accessToken'])
  if (accessToken === undefined) return undefined
  const expiresAtMs = timeToMs(value['expiredAt'] ?? value['expiresAt']) ?? 0
  const refreshExpiresAtMs = timeToMs(value['refreshExpiredAt'] ?? value['refreshExpiresAt'])
  const refreshToken = optionalString(value['refreshToken'])
  const account = typeof value['account'] === 'object' && value['account'] !== null && !Array.isArray(value['account'])
    ? value['account'] as Record<string, unknown>
    : undefined
  const accountName = optionalString(account?.['username'])
  return {
    accessToken,
    ...refreshToken === undefined ? {} : { refreshToken },
    userId: optionalString(value['userId']) ?? '',
    ...accountName === undefined ? {} : { accountName },
    host: optionalString(value['host']) ?? '',
    expiresAtMs,
    ...refreshExpiresAtMs === undefined ? {} : { refreshExpiresAtMs },
    edition,
    source,
  }
}

export function traeAccountId(credential: Pick<TraeCredential, 'edition' | 'userId' | 'accountName'>): string {
  const stable = `${credential.edition}\0${credential.userId || credential.accountName || 'unknown'}`
  return createHash('sha256').update(stable).digest('hex').slice(0, 24)
}

function parseOwn(text: string): TraeCredential | undefined {
  try {
    const document = JSON.parse(text) as { version?: unknown; credential?: unknown }
    if (document.version !== OWN_VERSION || typeof document.credential !== 'object' || document.credential === null) return undefined
    const stored = document.credential as Record<string, unknown>
    const edition = stored['edition']
    if (edition !== 'cn' && edition !== 'sg' && edition !== 'solo' && edition !== 'solo-sg') return undefined
    return normalizeTraeCredential({
      token: stored['accessToken'], refreshToken: stored['refreshToken'], userId: stored['userId'], host: stored['host'],
      account: stored['accountName'] === undefined ? undefined : { username: stored['accountName'] },
      expiredAt: stored['expiresAtMs'], refreshExpiredAt: stored['refreshExpiresAtMs'],
    }, edition, 'dsh')
  } catch { return undefined }
}

export class TraeCredentialStore {
  private storagePathOverride: string | undefined
  private edition: TraeEdition | 'auto'
  private accountId: string | undefined
  private readonly ownPath: string
  private readonly refresh: TraeCredentialStoreOptions['refresh']
  private readonly refreshMarginMs: number
  private inflight: Promise<TraeCredential> | undefined

  constructor(options: TraeCredentialStoreOptions) {
    this.storagePathOverride = options.storagePath
    this.edition = options.edition ?? 'auto'
    this.accountId = options.accountId
    this.ownPath = options.ownPath ?? traeOwnAuthPath()
    this.refresh = options.refresh
    this.refreshMarginMs = options.refreshMarginMs ?? 5 * 60_000
  }

  setSource(storagePath: string | undefined, edition: TraeEdition | 'auto' = 'auto', accountId?: string): void {
    this.storagePathOverride = storagePath
    this.edition = edition
    this.accountId = accountId
    this.inflight = undefined
  }

  selectAccount(accountId: string | undefined): void {
    this.accountId = accountId
    this.inflight = undefined
  }

  candidates(): TraeStorageCandidate[] {
    if (this.storagePathOverride !== undefined) {
      const edition = this.edition === 'auto' ? 'cn' : this.edition
      return [{ edition, path: this.storagePathOverride }]
    }
    const all = traeStorageCandidates()
    // This connector targets the CN service and Work-credit contracts only.
    // Ignore SG installations even when they are signed in locally.
    return this.edition === 'auto'
      ? all.filter(candidate => candidate.edition === 'cn' || candidate.edition === 'solo')
      : all.filter(candidate => candidate.edition === this.edition && (candidate.edition === 'cn' || candidate.edition === 'solo'))
  }

  /**
   * Deterministic default when no account is explicitly selected: the first
   * discovered account. This is NOT credit-seeking — it never reorders accounts
   * to find one with general credits. The plugin bills exactly the account the
   * user selected, or the first account when nothing has been selected yet.
   */
  private preferred(credentials: TraeCredential[]): TraeCredential | undefined {
    return credentials[0]
  }

  async accounts(): Promise<TraeAccountChoice[]> {
    const credentials = await this.readAll()
    const selectedExists = this.accountId !== undefined && credentials.some(credential => traeAccountId(credential) === this.accountId)
    const defaultSelected = this.preferred(credentials)
    return credentials.map(credential => ({
      id: traeAccountId(credential),
      accountName: credential.accountName ?? (credential.userId || `${credential.edition} account`),
      edition: credential.edition,
      source: credential.source,
      tokenExpiresAtMs: credential.expiresAtMs,
      selected: selectedExists ? traeAccountId(credential) === this.accountId : credential === defaultSelected,
    }))
  }

  async current(): Promise<TraeCredential | undefined> {
    const credentials = await this.readAll()
    if (this.accountId === undefined) return this.preferred(credentials)
    const selected = credentials.find(credential => traeAccountId(credential) === this.accountId)
    // A saved account can disappear when Trae replaces its local login. Do NOT
    // silently fall back to a different account: that would bill a different
    // account than the one the user explicitly selected. Return undefined so the
    // caller surfaces "no signed-in account" and the user can re-select, instead
    // of the plugin quietly switching accounts behind their back.
    return selected
  }

  async resolve(): Promise<TraeCredential> {
    const credential = await this.current()
    if (credential === undefined) throw new Error(`trae: no signed-in account found (${this.candidates().map(item => item.path).join(' or ')})`)
    if (credential.expiresAtMs > Date.now() + this.refreshMarginMs) return credential
    this.inflight ??= this.refreshNow(credential).finally(() => { this.inflight = undefined })
    return this.inflight
  }

  async status(): Promise<{ state: 'signed-in' | 'signed-out'; edition?: TraeEdition; expiresAtMs?: number; source?: 'desktop' | 'dsh' }> {
    try {
      const value = await this.current()
      return value === undefined ? { state: 'signed-out' } : { state: 'signed-in', edition: value.edition, expiresAtMs: value.expiresAtMs, source: value.source }
    } catch { return { state: 'signed-out' } }
  }

  async desktopFilePresent(): Promise<boolean> {
    for (const candidate of this.candidates()) {
      try { if ((await stat(candidate.path)).isFile()) return true } catch {}
    }
    return false
  }

  async logout(): Promise<void> {
    await rm(this.ownPath, { force: true })
    await rm(`${this.ownPath}.lock`, { force: true })
  }

  private async readAll(): Promise<TraeCredential[]> {
    const desktop = await this.readDesktopAll()
    const own = await this.readOwn()
    const cnOwn = own?.edition === 'cn' || own?.edition === 'solo' ? own : undefined
    if (cnOwn === undefined || desktop.some(credential => traeAccountId(credential) === traeAccountId(cnOwn))) return desktop
    return [...desktop, cnOwn]
  }

  private async readDesktopAll(): Promise<TraeCredential[]> {
    const credentials: TraeCredential[] = []
    for (const candidate of this.candidates()) {
      try {
        const raw = parseTraeStorageDocument(await readFile(candidate.path, 'utf8'))
        const credential = normalizeTraeCredential(raw, candidate.edition, 'desktop')
        if (credential !== undefined && !credentials.some(existing => traeAccountId(existing) === traeAccountId(credential))) credentials.push(credential)
      } catch {
        // One stale, partially written, unsupported, or signed-out Trae edition
        // must not hide valid accounts from the other local installations.
        continue
      }
    }
    return credentials
  }

  private async readOwn(): Promise<TraeCredential | undefined> {
    try { return parseOwn(await readFile(this.ownPath, 'utf8')) }
    catch { return undefined }
  }

  private async refreshNow(credential: TraeCredential): Promise<TraeCredential> {
    if (credential.refreshToken === undefined || (credential.refreshExpiresAtMs !== undefined && credential.refreshExpiresAtMs <= Date.now())) {
      if (credential.expiresAtMs > Date.now() + 30_000) return credential
      throw new Error('trae: access token expired and no valid refresh token is available; sign in again in Trae')
    }
    try {
      const outcome = await this.refresh(credential)
      const refreshed: TraeCredential = {
        ...credential,
        accessToken: outcome.accessToken,
        ...outcome.refreshToken === undefined ? {} : { refreshToken: outcome.refreshToken },
        expiresAtMs: outcome.expiresAtMs,
        ...outcome.refreshExpiresAtMs === undefined ? {} : { refreshExpiresAtMs: outcome.refreshExpiresAtMs },
        ...outcome.host === undefined ? {} : { host: outcome.host },
        source: 'dsh',
      }
      await withFileLock(this.ownPath, async () => {
        await writeFileAtomic(this.ownPath, `${JSON.stringify({ version: OWN_VERSION, credential: refreshed }, null, 2)}\n`, { mode: 0o600, dirMode: 0o700 })
      })
      return refreshed
    } catch (error: unknown) {
      if (credential.expiresAtMs > Date.now() + 30_000) return credential
      throw new Error(`trae: token refresh failed and access token is expired (${String(error)}); sign in again in Trae`)
    }
  }
}
