import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  appVersionPath,
  appUserAgent,
  readBundleVersion,
  resolveAppVersion,
  validAppVersion,
  FALLBACK_APP_VERSION,
} from '../src/app-version.ts'

/**
 * The App version is only ever a User-Agent component for the international
 * catalog request. These tests pin the three things that make it safe: the
 * value never comes from a guess, a bad value can never reach an HTTP header,
 * and a missing App degrades instead of failing the catalog.
 */

const CLEANUP: (() => Promise<void>)[] = []

afterEach(async () => {
  for (const dispose of CLEANUP.splice(0)) await dispose()
})

async function tempPath(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), 'wb-appversion-'))
  CLEANUP.push(() => rm(root, { recursive: true, force: true }))
  return join(root, 'version.json')
}

describe('validAppVersion', () => {
  it('accepts only dotted numeric versions', () => {
    expect(validAppVersion('5.5.2')).toBe(true)
    expect(validAppVersion('5.5.2.1')).toBe(true)
    // Two segments are accepted: the App's own version has three, but a
    // two-part value is a legitimate version rather than a malformed one, and
    // rejecting it would only risk the fallback being used needlessly.
    expect(validAppVersion('5.5')).toBe(true)
    // Rejected because the value reaches a header: anything carrying CR, LF,
    // spaces, or extra UA tokens could split the request or forge a second
    // product token in the User-Agent.
    expect(validAppVersion('5.5.2\r\nX-Injected: 1')).toBe(false)
    expect(validAppVersion('5.5.2 WorkBuddy/9.9')).toBe(false)
    expect(validAppVersion('v5.5.2')).toBe(false)
    expect(validAppVersion('5')).toBe(false)
    expect(validAppVersion('')).toBe(false)
    expect(validAppVersion(5.5)).toBe(false)
    expect(validAppVersion(undefined)).toBe(false)
  })
})

describe('appUserAgent', () => {
  it('builds the form measured to reach the App catalog document', () => {
    // `WorkBuddyAI/5.5.2` returned 200 with the 21-model App document on
    // 2026-09-11; the space form `WorkBuddy AI/5.5.2` returned 400/12403.
    // This pin exists so nobody "restores" the space from the older prose.
    expect(appUserAgent('5.5.2')).toBe('WorkBuddyAI/5.5.2')
    expect(appUserAgent('5.5.2')).not.toContain(' ')
  })

  it('refuses to interpolate an invalid version into a header', () => {
    expect(() => appUserAgent('5.5.2\r\nX: 1')).toThrow()
    expect(() => appUserAgent('latest')).toThrow()
  })
})

describe('readBundleVersion', () => {
  it('reads CFBundleShortVersionString out of a plist', async () => {
    const plist = await tempPath()
    await writeFile(plist, [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<plist version="1.0"><dict>',
      '<key>CFBundleName</key><string>WorkBuddy AI</string>',
      '<key>CFBundleShortVersionString</key><string>5.5.2</string>',
      '<key>CFBundleVersion</key><string>9999</string>',
      '</dict></plist>',
    ].join('\n'))
    // Reads the requested key, not the first <string> in the file.
    await expect(readBundleVersion(plist)).resolves.toBe('5.5.2')
  })

  it('returns undefined for a missing file, a binary plist, or a bad value', async () => {
    await expect(readBundleVersion('/nonexistent/Info.plist')).resolves.toBeUndefined()

    const binary = await tempPath()
    await writeFile(binary, Buffer.from([0x62, 0x70, 0x6c, 0x69, 0x73, 0x74, 0x00]))
    await expect(readBundleVersion(binary)).resolves.toBeUndefined()

    const empty = await tempPath()
    await writeFile(empty, '<plist><dict><key>CFBundleShortVersionString</key><string></string></dict></plist>')
    await expect(readBundleVersion(empty)).resolves.toBeUndefined()
  })
})

describe('resolveAppVersion', () => {
  it('prefers the installed App and caches the value it read', async () => {
    const path = await tempPath()
    const installed = vi.fn(async () => ({ version: '5.5.9', bundle: '/Applications/WorkBuddy AI.app' }))
    await expect(resolveAppVersion({ installed, path })).resolves.toEqual({
      version: '5.5.9',
      source: 'installed',
      bundle: '/Applications/WorkBuddy AI.app',
    })
    // The cache is what makes an uninstalled App survivable.
    await expect(resolveAppVersion({ installed: async () => undefined, path })).resolves.toEqual({
      version: '5.5.9',
      source: 'saved',
    })
  })

  it('falls back to the compiled-in value when there is no App and no cache', async () => {
    const path = await tempPath()
    await expect(resolveAppVersion({ installed: async () => undefined, path })).resolves.toEqual({
      version: FALLBACK_APP_VERSION,
      source: 'fallback',
    })
  })

  it('ignores a corrupt cache rather than sending it upstream', async () => {
    const path = await tempPath()
    await writeFile(path, JSON.stringify({ version: 'not-a-version' }))
    await expect(resolveAppVersion({ installed: async () => undefined, path })).resolves.toEqual({
      version: FALLBACK_APP_VERSION,
      source: 'fallback',
    })

    await writeFile(path, 'not json at all')
    await expect(resolveAppVersion({ installed: async () => undefined, path })).resolves.toEqual({
      version: FALLBACK_APP_VERSION,
      source: 'fallback',
    })
  })

  it('still answers when the cache cannot be written', async () => {
    // A read-only home must not take the catalog down with it.
    await expect(resolveAppVersion({
      installed: async () => ({ version: '5.5.2', bundle: '/x' }),
      path: '/proc/definitely-not-writable/version.json',
    })).resolves.toMatchObject({ version: '5.5.2', source: 'installed' })
  })

  it('defaults its cache path under the DSH home', () => {
    expect(appVersionPath()).toMatch(/\.workbuddy-ai-version\.json$/)
  })
})
