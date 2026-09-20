import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { FALLBACK_APP_VERSION, type AppVersionInfo } from '../src/app-version.ts'
import {
  FALLBACK_CN_APP_VERSION,
  chatUserAgent,
  readCliVersion,
  resolveChatIdentity,
  validCliVersion,
} from '../src/client-identity.ts'

/**
 * Offline tests for the chat identity (plan §3, 阶段一离线检查): every
 * filesystem read is injected or pointed at a temp directory, so nothing here
 * depends on an installed App or a real home.
 */

const CLEANUP: (() => Promise<void>)[] = []

afterEach(async () => {
  for (const dispose of CLEANUP.splice(0)) await dispose()
})

async function tempDir(prefix: string): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), prefix))
  CLEANUP.push(() => rm(root, { recursive: true, force: true }))
  return root
}

/** Materialize a fake bundle whose `cli/package.json` holds the given content. */
async function bundleWithCliPackage(pkg: unknown): Promise<string> {
  const root = await tempDir('wb-cli-')
  const cli = join(root, 'Contents', 'Resources', 'app.asar.unpacked', 'cli')
  await mkdir(cli, { recursive: true })
  await writeFile(join(cli, 'package.json'), typeof pkg === 'string' ? pkg : JSON.stringify(pkg), 'utf8')
  return root
}

describe('chatUserAgent', () => {
  it('composes the CN desktop form with both product tokens and the CLI segment', () => {
    expect(chatUserAgent({ clientVersion: '5.5.6', cliVersion: '2.137.1' }, 'cn'))
      .toBe('WorkBuddy/5.5.6 WorkBuddy/5.5.6 CLI/2.137.1')
  })

  it('names the international product in the second token only', () => {
    expect(chatUserAgent({ clientVersion: '5.5.2', cliVersion: '5.5.2' }, 'global'))
      .toBe('WorkBuddy/5.5.2 WorkBuddy AI/5.5.2 CLI/5.5.2')
  })

  it('omits the CLI segment when no CLI version resolved', () => {
    expect(chatUserAgent({ clientVersion: '5.5.6' }, 'cn')).toBe('WorkBuddy/5.5.6 WorkBuddy/5.5.6')
  })

  it('rejects values that could break a header rather than interpolating them', () => {
    expect(() => chatUserAgent({ clientVersion: '5.5.6 x' }, 'cn')).toThrow()
    expect(() => chatUserAgent({ clientVersion: '5.5.6\nX: 1' }, 'cn')).toThrow()
    expect(() => chatUserAgent({ clientVersion: '5.5.6', cliVersion: '2.137.1 rm' }, 'cn')).toThrow()
  })
})

describe('validCliVersion', () => {
  it('accepts plain and prerelease versions, rejects anything header-hostile', () => {
    expect(validCliVersion('2.137.1')).toBe(true)
    expect(validCliVersion('2.137.1-rc.1')).toBe(true)
    expect(validCliVersion('0.0.0')).toBe(true)
    expect(validCliVersion('')).toBe(false)
    expect(validCliVersion('2.137.1 x')).toBe(false)
    expect(validCliVersion(undefined)).toBe(false)
  })
})

describe('readCliVersion', () => {
  it('prefers a valid non-placeholder version', async () => {
    const bundle = await bundleWithCliPackage({
      version: '3.0.0',
      publishConfig: { customPackage: { version: '2.137.1' } },
    })
    expect(await readCliVersion(bundle)).toBe('3.0.0')
  })

  it('falls back to publishConfig.customPackage.version for the 0.0.0 placeholder', async () => {
    const bundle = await bundleWithCliPackage({
      version: '0.0.0',
      publishConfig: { customPackage: { version: '2.137.1' } },
    })
    expect(await readCliVersion(bundle)).toBe('2.137.1')
  })

  it('yields undefined for unreadable, malformed, or invalid metadata', async () => {
    expect(await readCliVersion(join(await tempDir('wb-cli-'), 'no-such-bundle'))).toBeUndefined()
    expect(await readCliVersion(await bundleWithCliPackage('not json'))).toBeUndefined()
    expect(await readCliVersion(await bundleWithCliPackage({ version: '2.137.1 oops' }))).toBeUndefined()
  })
})

describe('resolveChatIdentity (CN)', () => {
  it('uses the installed bundle and reads its CLI version, but persists the App version only', async () => {
    const dir = await tempDir('wb-cn-')
    const saved = join(dir, 'cn.json')
    const identity = await resolveChatIdentity('cn', {
      installedCn: async () => ({ version: '5.5.6', bundle: join(dir, 'WorkBuddy.app') }),
      cliVersion: async () => '2.137.1',
      cnSavedPath: saved,
    })
    expect(identity).toEqual({ clientVersion: '5.5.6', cliVersion: '2.137.1' })
    const persisted = JSON.parse(await readFile(saved, 'utf8')) as Record<string, unknown>
    expect(persisted['version']).toBe('5.5.6')
    // The CLI version is read live from the bundle; the saved cache must not
    // resurrect it after the App is gone (plan: unreadable metadata omits
    // the CLI segment rather than claiming a version whose source is gone).
    expect('cliVersion' in persisted).toBe(false)
  })

  it('restores the saved App version without the CLI segment when no bundle is installed', async () => {
    const dir = await tempDir('wb-cn-')
    const saved = join(dir, 'cn.json')
    // A legacy cache shape that happens to carry a cliVersion must not leak it.
    await writeFile(saved, JSON.stringify({ version: '5.5.5', cliVersion: '2.0.0' }), 'utf8')
    await expect(resolveChatIdentity('cn', { installedCn: async () => undefined, cnSavedPath: saved }))
      .resolves.toEqual({ clientVersion: '5.5.5' })
    await expect(resolveChatIdentity('cn', { installedCn: async () => undefined, cnSavedPath: join(dir, 'absent.json') }))
      .resolves.toEqual({ clientVersion: FALLBACK_CN_APP_VERSION })
  })

  it('treats a corrupt or wrong-shaped saved cache as absent', async () => {
    const dir = await tempDir('wb-cn-')
    const saved = join(dir, 'cn.json')
    await writeFile(saved, '{"version":"5.5.5","cliVersion":"res', 'utf8')
    await expect(resolveChatIdentity('cn', { installedCn: async () => undefined, cnSavedPath: saved }))
      .resolves.toEqual({ clientVersion: FALLBACK_CN_APP_VERSION })
    await writeFile(saved, JSON.stringify({ nope: true }), 'utf8')
    await expect(resolveChatIdentity('cn', { installedCn: async () => undefined, cnSavedPath: saved }))
      .resolves.toEqual({ clientVersion: FALLBACK_CN_APP_VERSION })
  })

  it('rejects an installed version that cannot reach a header', async () => {
    const dir = await tempDir('wb-cn-')
    await expect(resolveChatIdentity('cn', {
      installedCn: async () => ({ version: '5.5.6 x', bundle: dir }),
      cliVersion: async () => '2.137.1',
      cnSavedPath: join(dir, 'cn.json'),
    })).resolves.toEqual({ clientVersion: FALLBACK_CN_APP_VERSION })
  })

  it('returns the identity even when the cache write fails', async () => {
    const dir = await tempDir('wb-cn-')
    const blocker = join(dir, 'blocker')
    await writeFile(blocker, 'regular file', 'utf8')
    await expect(resolveChatIdentity('cn', {
      installedCn: async () => ({ version: '5.5.6', bundle: dir }),
      cliVersion: async () => '2.137.1',
      cnSavedPath: join(blocker, 'under', 'a', 'file.json'),
    })).resolves.toEqual({ clientVersion: '5.5.6', cliVersion: '2.137.1' })
  })

  it('degrades a throwing reader to the built-in fallback instead of throwing', async () => {
    const dir = await tempDir('wb-cn-')
    await expect(resolveChatIdentity('cn', {
      installedCn: async () => {
        throw new Error('unexpected fs error')
      },
      cnSavedPath: join(dir, 'cn.json'),
    })).resolves.toEqual({ clientVersion: FALLBACK_CN_APP_VERSION })
    await expect(resolveChatIdentity('global', {
      resolveIntl: async () => {
        throw new Error('unexpected fs error')
      },
    })).resolves.toEqual({ clientVersion: FALLBACK_APP_VERSION })
  })
})

describe('resolveChatIdentity (international)', () => {
  const INTL_BUNDLE = '/Applications/WorkBuddy AI.app'
  const intlInstalled: AppVersionInfo = { version: '5.5.2', source: 'installed', bundle: INTL_BUNDLE }

  it('reuses the app-version chain and reads the CLI version from the reported bundle', async () => {
    let cnProbeRuns = 0
    const dir = await tempDir('wb-intl-')
    const identity = await resolveChatIdentity('global', {
      resolveIntl: async () => intlInstalled,
      cliVersion: async bundle => (bundle === INTL_BUNDLE ? '5.5.2' : undefined),
      installedCn: async () => {
        cnProbeRuns += 1
        return undefined
      },
      cnSavedPath: join(dir, 'cn.json'),
    })
    expect(identity).toEqual({ clientVersion: '5.5.2', cliVersion: '5.5.2' })
    // The international path never consults the CN probe or the CN cache.
    expect(cnProbeRuns).toBe(0)
    await expect(readFile(join(dir, 'cn.json'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('drops the CLI segment when the chain reports no installed bundle (saved/fallback)', async () => {
    await expect(resolveChatIdentity('global', {
      resolveIntl: async () => ({ version: '5.5.2', source: 'saved' }),
    })).resolves.toEqual({ clientVersion: '5.5.2' })
    await expect(resolveChatIdentity('global', {
      resolveIntl: async () => ({ version: 'garbage', source: 'saved' }),
    })).resolves.toEqual({ clientVersion: FALLBACK_APP_VERSION })
  })
})
