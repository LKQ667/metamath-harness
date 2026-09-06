import { mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { normalizeTraeCredential, TraeCredentialStore } from '../src/auth.ts'
import { TRAE_AUTH_STORAGE_KEY } from '../src/decrypt.ts'

const cleanup: string[] = []
afterEach(async () => { await Promise.all(cleanup.splice(0).map(path => rm(path, { recursive: true, force: true }))) })

function storage(token: string, expiresAt: number, refreshExpiresAt = Date.now() + 86_400_000, userId = 'uid'): string {
  return JSON.stringify({ [TRAE_AUTH_STORAGE_KEY]: JSON.stringify({
    token, refreshToken: 'rt', userId, account: { username: userId }, host: 'https://api.trae.cn', expiredAt: new Date(expiresAt).toISOString(), refreshExpiredAt: new Date(refreshExpiresAt).toISOString(),
  }) })
}

async function temp(): Promise<string> { const dir = await mkdtemp(join(tmpdir(), 'trae-auth-')); cleanup.push(dir); return dir }

describe('Trae credential normalization', () => {
  it('normalizes ISO and numeric expiries while exposing only the display username', () => {
    expect(normalizeTraeCredential({ token: 'at', expiredAt: '2030-01-01T00:00:00.000Z', account: { username: 'LaoDing', email: 'private@example.com' } }, 'cn', 'desktop')).toMatchObject({
      accessToken: 'at', accountName: 'LaoDing', edition: 'cn', source: 'desktop', expiresAtMs: Date.parse('2030-01-01T00:00:00.000Z'),
    })
    expect(normalizeTraeCredential({}, 'cn', 'desktop')).toBeUndefined()
  })
})

describe('TraeCredentialStore', () => {
  it('reads desktop storage without modifying it', async () => {
    const dir = await temp(); const file = join(dir, 'storage.json'); const before = storage('desktop', Date.now() + 3_600_000)
    await writeFile(file, before)
    const store = new TraeCredentialStore({ storagePath: file, edition: 'cn', ownPath: join(dir, 'own.json'), refresh: async () => { throw new Error('unused') } })
    await expect(store.resolve()).resolves.toMatchObject({ accessToken: 'desktop', source: 'desktop', edition: 'cn' })
    expect(await readFile(file, 'utf8')).toBe(before)
  })

  it('single-flights refresh, stores a 0600 copy, and serves it next', async () => {
    const dir = await temp(); const file = join(dir, 'storage.json'); const own = join(dir, 'own.json')
    await writeFile(file, storage('old', Date.now() - 1000))
    let refreshes = 0
    const store = new TraeCredentialStore({ storagePath: file, edition: 'cn', ownPath: own, refresh: async () => {
      refreshes += 1; await new Promise(resolve => setTimeout(resolve, 10)); return { accessToken: 'fresh', refreshToken: 'rt2', expiresAtMs: Date.now() + 3_600_000 }
    } })
    const [a, b] = await Promise.all([store.resolve(), store.resolve()])
    expect(a.accessToken).toBe('fresh'); expect(b.accessToken).toBe('fresh'); expect(refreshes).toBe(1)
    // File permission bits are POSIX-only; Windows exposes no meaningful mode.
    if (process.platform !== 'win32') {
      expect((await stat(own)).mode & 0o777).toBe(0o600)
    }
    expect(JSON.parse(await readFile(own, 'utf8')).credential.accessToken).toBe('fresh')
  })

  it('prefers the desktop credential even when the own cache expires later', async () => {
    const dir = await temp(); const file = join(dir, 'storage.json'); const own = join(dir, 'own.json')
    await writeFile(file, storage('desktop', Date.now() + 3_600_000))
    await writeFile(own, JSON.stringify({ version: 1, credential: {
      accessToken: 'stale-own', refreshToken: 'rt', userId: 'old', host: 'https://api.trae.cn',
      expiresAtMs: Date.now() + 86_400_000, source: 'dsh', edition: 'cn',
    } }))
    const store = new TraeCredentialStore({ storagePath: file, edition: 'cn', ownPath: own, refresh: async () => { throw new Error('unused') } })
    // The desktop credential (the account currently signed in to Trae) must win,
    // even though the own cache has a later expiry: the plugin should always
    // follow the account the user is logged into right now.
    await expect(store.current()).resolves.toMatchObject({ accessToken: 'desktop', source: 'desktop' })
  })

  it('uses a still-valid token when refresh fails and rejects an expired refresh token', async () => {
    const dir = await temp(); const fresh = join(dir, 'fresh.json'); const expired = join(dir, 'expired.json')
    await writeFile(fresh, storage('usable', Date.now() + 60_000))
    const fallback = new TraeCredentialStore({ storagePath: fresh, edition: 'cn', ownPath: join(dir, 'own-a'), refreshMarginMs: 300_000, refresh: async () => { throw new Error('down') } })
    await expect(fallback.resolve()).resolves.toMatchObject({ accessToken: 'usable' })
    await writeFile(expired, storage('dead', Date.now() - 1000, Date.now() - 1000))
    const rejected = new TraeCredentialStore({ storagePath: expired, edition: 'cn', ownPath: join(dir, 'own-b'), refresh: async () => ({ accessToken: 'never', expiresAtMs: Date.now() + 1000 }) })
    await expect(rejected.resolve()).rejects.toThrow(/no valid refresh token/)
  })

  it('discovers multiple local editions and selects by stable account id', async () => {
    const dir = await temp()
    const cn = join(dir, 'cn.json'); const solo = join(dir, 'solo.json')
    await writeFile(cn, storage('cn-token', Date.now() + 3_600_000, undefined, 'cn-user'))
    await writeFile(solo, storage('solo-token', Date.now() + 3_600_000, undefined, 'solo-user'))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    store.candidates = () => [{ edition: 'cn', path: cn }, { edition: 'solo', path: solo }]
    const accounts = await store.accounts()
    expect(accounts).toHaveLength(2)
    expect(accounts.map(account => account.accountName)).toEqual(['cn-user', 'solo-user'])
    store.selectAccount(accounts[1]!.id)
    await expect(store.resolve()).resolves.toMatchObject({ userId: 'solo-user', accessToken: 'solo-token' })
    expect((await store.accounts())[1]?.selected).toBe(true)
  })

  it('defaults to the first discovered account, never credit-seeking, when none is selected', async () => {
    const dir = await temp()
    const cn = join(dir, 'cn.json'); const solo = join(dir, 'solo.json')
    await writeFile(cn, storage('cn-token', Date.now() + 3_600_000, undefined, 'cn-user'))
    await writeFile(solo, storage('solo-token', Date.now() + 3_600_000, undefined, 'solo-user'))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    store.candidates = () => [{ edition: 'cn', path: cn }, { edition: 'solo', path: solo }]
    // No explicit selection: the FIRST account (cn-user) is used, regardless of
    // which account might have credits. The plugin must not hunt for credits.
    await expect(store.current()).resolves.toMatchObject({ userId: 'cn-user' })
    expect((await store.accounts()).find(account => account.accountName === 'cn-user')?.selected).toBe(true)
  })

  it('does not fall back to another account when the selected account disappears', async () => {
    const dir = await temp()
    const cn = join(dir, 'cn.json'); const solo = join(dir, 'solo.json')
    await writeFile(cn, storage('cn-token', Date.now() + 3_600_000, undefined, 'cn-user'))
    await writeFile(solo, storage('solo-token', Date.now() + 3_600_000, undefined, 'solo-user'))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    store.candidates = () => [{ edition: 'cn', path: cn }, { edition: 'solo', path: solo }]
    const soloId = (await store.accounts()).find(account => account.accountName === 'solo-user')!.id
    store.selectAccount(soloId)
    await expect(store.current()).resolves.toMatchObject({ userId: 'solo-user' })
    // Remove the selected account's file: selection must NOT silently switch
    // to the remaining account; it must surface as "not found".
    await rm(solo)
    await expect(store.current()).resolves.toBeUndefined()
  })

  it('auto mode includes CN editions only', () => {
    const store = new TraeCredentialStore({ ownPath: '/tmp/unused-trae-own', refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    expect(store.candidates().map(candidate => candidate.edition)).toEqual(['cn', 'solo'])
  })

  it('skips a malformed edition instead of hiding valid accounts', async () => {
    const dir = await temp()
    const bad = join(dir, 'bad.json'); const good = join(dir, 'good.json')
    await writeFile(bad, '{broken')
    await writeFile(good, storage('good-token', Date.now() + 3_600_000, undefined, 'good-user'))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    store.candidates = () => [{ edition: 'cn', path: bad }, { edition: 'solo', path: good }]
    await expect(store.accounts()).resolves.toMatchObject([{ accountName: 'good-user', edition: 'solo' }])
  })

  it('does not fall back when the saved account no longer exists', async () => {
    const dir = await temp(); const file = join(dir, 'current.json')
    await writeFile(file, storage('current-token', Date.now() + 3_600_000, undefined, 'current-user'))
    const store = new TraeCredentialStore({ storagePath: file, edition: 'solo', accountId: 'removed-account', ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    // The explicitly selected account id is gone. The plugin must NOT silently
    // switch to another live account; it surfaces "no signed-in account" so the
    // user can re-select instead of being billed against a different account.
    await expect(store.resolve()).rejects.toThrow(/no signed-in account found/)
  })

  it('reports signed out for a missing explicit file', async () => {
    const dir = await temp()
    const store = new TraeCredentialStore({ storagePath: join(dir, 'missing.json'), edition: 'cn', ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    await expect(store.status()).resolves.toEqual({ state: 'signed-out' })
    await expect(store.desktopFilePresent()).resolves.toBe(false)
  })
})
