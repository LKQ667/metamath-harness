import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
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
    store.candidates = () => [{ edition: 'cn', path: cn, source: 'desktop' }, { edition: 'solo', path: solo, source: 'desktop' }]
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
    store.candidates = () => [{ edition: 'cn', path: cn, source: 'desktop' }, { edition: 'solo', path: solo, source: 'desktop' }]
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
    store.candidates = () => [{ edition: 'cn', path: cn, source: 'desktop' }, { edition: 'solo', path: solo, source: 'desktop' }]
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
    const editions = store.candidates().map(candidate => candidate.edition)
    // The CLI dotfile home contributes an extra `cn` candidate, so the exact
    // list is asserted as a set of editions rather than a fixed sequence.
    expect(new Set(editions)).toEqual(new Set(['cn', 'solo']))
    expect(editions).not.toContain('sg')
    expect(editions).not.toContain('solo-sg')
  })

  it('skips a malformed edition instead of hiding valid accounts', async () => {
    const dir = await temp()
    const bad = join(dir, 'bad.json'); const good = join(dir, 'good.json')
    await writeFile(bad, '{broken')
    await writeFile(good, storage('good-token', Date.now() + 3_600_000, undefined, 'good-user'))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async c => ({ accessToken: c.accessToken, expiresAtMs: c.expiresAtMs }) })
    store.candidates = () => [{ edition: 'cn', path: bad, source: 'desktop' }, { edition: 'solo', path: good, source: 'desktop' }]
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

describe('TraeCredentialStore with a CLI-only sign-in', () => {
  const cliJwt = (userId: string, exp: number): string =>
    `${Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ data: { user_id: userId }, iss: 'trae', exp })).toString('base64url')}.sig`

  it('resolves an account from a CLI token with no storage.json present', async () => {
    // Issue #5 regression: on WSL2 the user signs in with `traecli`, which never
    // writes a globalStorage/storage.json. Before CLI candidates existed the
    // store found nothing and the plugin reported "not signed in" forever.
    const dir = await temp(); const token = join(dir, 'trae-jwt-token')
    await writeFile(token, `${cliJwt('4162118908394475', Math.floor((Date.now() + 86_400_000) / 1000))}\n`)
    const store = new TraeCredentialStore({ storagePath: token, edition: 'cn', ownPath: join(dir, 'own'), refresh: async () => { throw new Error('unused') } })
    const credential = await store.resolve()
    expect(credential).toMatchObject({ userId: '4162118908394475', source: 'cli', edition: 'cn' })
    // The CLI token has no host claim, so the CN host is supplied rather than an
    // empty string that would become an unusable base URL.
    expect(credential.host).toBe('https://api.trae.cn')
    expect(credential.expiresAtMs).toBeGreaterThan(Date.now())
  })

  it('lets a CLI sign-in be selected as an account', async () => {
    const dir = await temp(); const token = join(dir, 'trae-jwt-token')
    await writeFile(token, cliJwt('cli-user', Math.floor((Date.now() + 86_400_000) / 1000)))
    const store = new TraeCredentialStore({ storagePath: token, edition: 'cn', ownPath: join(dir, 'own'), refresh: async () => { throw new Error('unused') } })
    const accounts = await store.accounts()
    expect(accounts).toHaveLength(1)
    expect(accounts[0]).toMatchObject({ source: 'cli', selected: true })
  })

  it('explains why every candidate failed instead of reporting a bare signed-out', async () => {
    // The original silent `catch { continue }` made a wrong-path machine
    // undiagnosable. `diagnose()` must name each tried path and its failure.
    const dir = await temp()
    const missing = join(dir, 'absent', 'trae-jwt-token')
    const broken = join(dir, 'broken', 'trae-jwt-token')
    await mkdir(join(dir, 'broken'), { recursive: true })
    await writeFile(broken, 'not-a-jwt')
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async () => { throw new Error('unused') } })
    store.candidates = () => [
      { edition: 'cn', path: missing, source: 'cli' },
      { edition: 'cn', path: broken, source: 'cli' },
    ]
    await expect(store.status()).resolves.toEqual({ state: 'signed-out' })
    const { tried, failures } = await store.diagnose()
    expect(tried.map(item => item.path)).toEqual([missing, broken])
    expect(failures).toHaveLength(2)
    expect(failures[0]).toMatchObject({ path: missing, reason: 'missing' })
    expect(failures[1]).toMatchObject({ path: broken, reason: 'invalid' })
    expect(failures[1]?.message).toMatch(/three-part/)
  })

  it('reports no failure for a candidate that yields an account', async () => {
    const dir = await temp(); const token = join(dir, 'trae-jwt-token')
    await writeFile(token, cliJwt('ok-user', Math.floor((Date.now() + 86_400_000) / 1000)))
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async () => { throw new Error('unused') } })
    store.candidates = () => [{ edition: 'cn', path: token, source: 'cli' }]
    const { failures } = await store.diagnose()
    expect(failures).toEqual([])
  })

  it('never leaks token material through the diagnostic payload', async () => {
    // The diagnostic crosses to the browser, so it must carry paths and fixed
    // reason strings only. Parser errors are written to never echo their input.
    const dir = await temp()
    const secret = 'eyJhbGciOiJSUzI1NiJ9.SUPERSECRETPAYLOAD.signature'
    const file = join(dir, 'token')
    await writeFile(file, `${secret}.${secret}`)
    const store = new TraeCredentialStore({ ownPath: join(dir, 'own'), refresh: async () => { throw new Error('unused') } })
    store.candidates = () => [{ edition: 'cn', path: file, source: 'cli' }]
    const { failures } = await store.diagnose()
    const serialized = JSON.stringify(failures)
    expect(serialized).not.toContain('SUPERSECRETPAYLOAD')
    expect(serialized).not.toContain(secret)
    expect(failures[0]?.reason).toBe('invalid')
  })
})
