/**
 * The desktop-client identity chat requests present as (phase 1 of
 * `docs/upstream-identity-alignment-plan.md`).
 *
 * Chat and its probe sibling carry the User-Agent shape the official desktop
 * client composes — `WorkBuddy/<v> <product>/<v> CLI/<cli>` — where the
 * product token names the app that owns the region's requests: `WorkBuddy`
 * for CN, `WorkBuddy AI` for international. Versions come from the installed
 * App when it can be read, degrade to a per-region saved value, and finally
 * to a compiled-in constant. A CLI version that does not resolve drops the
 * `CLI/…` token instead of inventing one (the official client's own rule for
 * a missing extension).
 *
 * Scope: chat and probe requests ONLY. Refresh, catalog, and billing keep
 * the headers they have always sent; the plan holds the blast radius to this
 * one variable so the live verification matrix stays readable.
 *
 * @module dsh-workbuddy-connect/client-identity
 */

import { readFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { writeFileAtomic } from '@deepseek-ai/dsh-atomic-write'
import { resolveDshHome } from '@deepseek-ai/dsh-home-paths'
import {
  FALLBACK_APP_VERSION,
  readBundleVersion,
  resolveAppVersion,
  validAppVersion,
  type AppVersionInfo,
} from './app-version.ts'
import type { WorkBuddyRegion } from './upstream.ts'

/**
 * Compiled-in CN fallback for the `WorkBuddy/<v>` tokens.
 *
 * Observed on the CN desktop app installed here (research §3.1, verified
 * 2026-09-11); like the international fallback it is a shape requirement,
 * not a currency claim — the gateway has not been observed to branch on it.
 */
export const FALLBACK_CN_APP_VERSION = '5.5.6'

/**
 * Basename of the CN saved-version cache under `$DSH_HOME`.
 *
 * Deliberately not the international `.workbuddy-ai-version.json`: that file
 * feeds the international catalog's User-Agent, and a CN App writing its
 * version into it would relabel that request. The two caches stay isolated
 * the way the per-variant catalog files are.
 */
export const CN_APP_VERSION_FILENAME = '.workbuddy-app-version.json'

/** The resolved identity a chat request presents as. */
export interface ChatIdentity {
  /** Desktop App version; drives both `WorkBuddy/<v>` product tokens. */
  clientVersion: string
  /** Bundled agent-CLI version; absent drops the `CLI/…` UA token. */
  cliVersion?: string
}

/**
 * Whether a value is a CLI version that may reach a header.
 *
 * Tolerates a prerelease suffix (`2.137.1-rc.1`) because the bundled CLI's
 * own metadata uses that spelling; anything with whitespace, CR or LF never
 * passes — the value is interpolated into an HTTP header.
 */
export function validCliVersion(value: unknown): value is string {
  return typeof value === 'string' && /^\d{1,6}(?:\.\d{1,6}){1,3}(?:-[0-9A-Za-z.]+)?$/u.test(value)
}

/** macOS App-bundle roots, searched in the order `app-version.ts` uses. */
function macAppRoots(): string[] {
  return ['/Applications', join(homedir(), 'Applications')]
}

/** Path of the bundled agent CLI's package.json inside an App bundle. */
function cliPackagePath(bundle: string): string {
  return join(bundle, 'Contents', 'Resources', 'app.asar.unpacked', 'cli', 'package.json')
}

/**
 * The bundled agent CLI's real version, or `undefined` when it does not resolve.
 *
 * `cli/package.json` ships a `0.0.0` placeholder in `version` with the real
 * version in `publishConfig.customPackage.version`; a valid non-placeholder
 * `version` wins, otherwise the custom-package value applies, and unreadable
 * or invalid metadata yields `undefined` (the caller drops the `CLI/…` UA
 * token rather than guessing).
 */
export async function readCliVersion(bundle: string): Promise<string | undefined> {
  let document: unknown
  try {
    document = JSON.parse(await readFile(cliPackagePath(bundle), 'utf8'))
  } catch {
    return undefined
  }
  if (typeof document !== 'object' || document === null || Array.isArray(document)) return undefined
  const pkg = document as Record<string, unknown>
  const declared = pkg['version']
  if (validCliVersion(declared) && declared !== '0.0.0') return declared
  const publishConfig = pkg['publishConfig']
  const customPackage = typeof publishConfig === 'object' && publishConfig !== null && !Array.isArray(publishConfig)
    ? publishConfig as Record<string, unknown>
    : undefined
  const custom = typeof customPackage?.['customPackage'] === 'object' && customPackage['customPackage'] !== null
    && !Array.isArray(customPackage['customPackage'])
    ? customPackage['customPackage'] as Record<string, unknown>
    : undefined
  const customVersion = custom?.['version']
  return validCliVersion(customVersion) ? customVersion : undefined
}

/**
 * Build the chat User-Agent for one region.
 *
 * Throws on an invalid version rather than interpolating one into a header;
 * `resolveChatIdentity` never produces such an identity, so the throw is a
 * last gate against future call-site mistakes, not an expected path.
 */
export function chatUserAgent(identity: ChatIdentity, region: WorkBuddyRegion): string {
  if (!validAppVersion(identity.clientVersion)) {
    throw new Error(`invalid client version for chat User-Agent: ${JSON.stringify(identity.clientVersion)}`)
  }
  if (identity.cliVersion !== undefined && !validCliVersion(identity.cliVersion)) {
    throw new Error(`invalid CLI version for chat User-Agent: ${JSON.stringify(identity.cliVersion)}`)
  }
  const product = region === 'global' ? 'WorkBuddy AI' : 'WorkBuddy'
  const parts = [`WorkBuddy/${identity.clientVersion}`, `${product}/${identity.clientVersion}`]
  if (identity.cliVersion !== undefined) parts.push(`CLI/${identity.cliVersion}`)
  return parts.join(' ')
}

/** Constructor dependencies; every reader is injectable so tests never touch a real App or home. */
export interface ResolveChatIdentityOptions {
  /** Installed CN desktop-bundle reader; defaults to the macOS probe. */
  installedCn?: () => Promise<{ version: string; bundle: string } | undefined>
  /** International version resolver; defaults to `app-version.ts`'s chain. */
  resolveIntl?: () => Promise<AppVersionInfo>
  /** CLI-version reader; defaults to reading the bundle's `cli/package.json`. */
  cliVersion?: (bundle: string) => Promise<string | undefined>
  /** CN saved-cache path; defaults to `$DSH_HOME/.workbuddy-app-version.json`. */
  cnSavedPath?: string
}

/** The installed CN desktop bundle, or `undefined` when it is not installed (or not readable). */
async function installedCnApp(): Promise<{ version: string; bundle: string } | undefined> {
  if (process.platform !== 'darwin') return undefined
  for (const root of macAppRoots()) {
    const bundle = join(root, 'WorkBuddy.app')
    const version = await readBundleVersion(join(bundle, 'Contents', 'Info.plist'))
    if (version !== undefined) return { version, bundle }
  }
  return undefined
}

/** Default CN saved-cache path. */
function cnSavedVersionPath(): string {
  return join(resolveDshHome(), CN_APP_VERSION_FILENAME)
}

/**
 * Resolve the chat identity for one region: installed App → region's saved
 * value → compiled-in fallback. Never throws — a missing App, an unreadable
 * plist, a failed cache write, or a reader that throws outright all degrade
 * to {@link fallbackChatIdentity}; resolution never blocks a message.
 *
 * The production path caches per region (a message must not re-read the
 * install tree); any injected option bypasses the cache entirely so tests
 * with different readers cannot observe each other's resolutions.
 */
export async function resolveChatIdentity(
  region: WorkBuddyRegion,
  options: ResolveChatIdentityOptions = {},
): Promise<ChatIdentity> {
  const injectable = options.installedCn !== undefined
    || options.resolveIntl !== undefined
    || options.cliVersion !== undefined
    || options.cnSavedPath !== undefined
  if (!injectable) {
    const cached = cache.get(region)
    if (cached !== undefined) return cached
  }
  let identity: ChatIdentity
  try {
    identity = region === 'global'
      ? await resolveGlobalIdentity(options)
      : await resolveCnIdentity(options)
  } catch {
    // A reader that throws (unexpected filesystem error, injected test
    // double) must not block a message and must not pin this degraded
    // answer for the process lifetime: return the built-in fallback
    // without caching it, so a later call can resolve properly again.
    return fallbackChatIdentity(region)
  }
  if (!injectable) cache.set(region, identity)
  return identity
}

const cache = new Map<WorkBuddyRegion, ChatIdentity>()

/**
 * The region's compiled-in fallback identity: the desktop form with the
 * built-in version and no `CLI/…` segment. This is the single degraded
 * shape every failure path converges on — a thrown reader, an unreadable
 * bundle, or a missing cache all present this, never the legacy CLI UA.
 */
export function fallbackChatIdentity(region: WorkBuddyRegion): ChatIdentity {
  return { clientVersion: region === 'global' ? FALLBACK_APP_VERSION : FALLBACK_CN_APP_VERSION }
}

/** CN: installed `WorkBuddy.app` → CN saved cache → CN fallback. */
async function resolveCnIdentity(options: ResolveChatIdentityOptions): Promise<ChatIdentity> {
  const savedPath = options.cnSavedPath ?? cnSavedVersionPath()
  const installed = await (options.installedCn ?? installedCnApp)()
  if (installed !== undefined && validAppVersion(installed.version)) {
    const cliVersion = await (options.cliVersion ?? readCliVersion)(installed.bundle)
    const identity: ChatIdentity = {
      clientVersion: installed.version,
      ...(cliVersion !== undefined && validCliVersion(cliVersion) ? { cliVersion } : {}),
    }
    // Best-effort remember of the App version only: the CLI version is read
    // live from the bundle whenever the bundle exists, and once the App is
    // gone the plan's degradation omits the `CLI/…` token instead of
    // continuing to claim a version whose source no longer exists.
    try {
      await writeFileAtomic(
        savedPath,
        `${JSON.stringify({ version: identity.clientVersion, observedAt: Date.now() }, null, 2)}\n`,
        { mode: 0o600, dirMode: 0o700 },
      )
    } catch {
      // Identity resolved; losing the memory of it is not a failure.
    }
    return identity
  }
  try {
    const saved: unknown = JSON.parse(await readFile(savedPath, 'utf8'))
    if (typeof saved === 'object' && saved !== null && !Array.isArray(saved)) {
      const document = saved as Record<string, unknown>
      if (validAppVersion(document['version'])) {
        return { clientVersion: document['version'] }
      }
    }
  } catch {
    // Absent or malformed cache: fall through to the compiled-in constant.
  }
  return fallbackChatIdentity('cn')
}

/**
 * International: reuse `app-version.ts`'s installed → saved → fallback chain
 * (its cache format and the catalog's version source stay untouched). The
 * CLI version is read only when that chain reports the installed bundle; a
 * saved or fallback resolution has no bundle path and drops the `CLI/…` token.
 * The CN cache is never read or written on this path.
 */
async function resolveGlobalIdentity(options: ResolveChatIdentityOptions): Promise<ChatIdentity> {
  const info = await (options.resolveIntl ?? resolveAppVersion)()
  const clientVersion = validAppVersion(info.version) ? info.version : FALLBACK_APP_VERSION
  let cliVersion: string | undefined
  if (info.bundle !== undefined) {
    const read = await (options.cliVersion ?? readCliVersion)(info.bundle)
    if (read !== undefined && validCliVersion(read)) cliVersion = read
  }
  return { clientVersion, ...cliVersion === undefined ? {} : { cliVersion } }
}
