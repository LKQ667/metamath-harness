import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { cpus, homedir, release } from 'node:os'
import type { TraeEdition, TraeStorageCandidate } from './paths.ts'

export interface TraeIdentity {
  edition: TraeEdition
  machineId: string
  deviceId: string
  appVersion?: string
  buildVersion?: string
  deviceBrand?: string
  deviceCpu?: string
  osVersion?: string
  platform: NodeJS.Platform
}

function nonEmpty(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined
}

function deviceCenterId(storage: Record<string, unknown>): string | undefined {
  const prefix = 'iCubeAuthInfo://icube-dc:'
  const ids = Object.keys(storage).filter(key => key.startsWith(prefix)).map(key => key.slice(prefix.length)).filter(Boolean)
  return ids.length === 1 ? ids[0] : undefined
}

export interface TraeIdentityReadOptions {
  /** Platform override for testing; defaults to process.platform. */
  platform?: NodeJS.Platform
  /** Home-directory override for testing; defaults to homedir(). */
  home?: string
  /** Environment override for testing; defaults to process.env. */
  env?: NodeJS.ProcessEnv
}

/** Read stable identity from Trae-owned files without generating impersonated IDs. */
export async function readTraeIdentity(candidate: TraeStorageCandidate, options: TraeIdentityReadOptions = {}): Promise<TraeIdentity> {
  const platform = options.platform ?? process.platform
  const home = options.home ?? homedir()
  const env = options.env ?? process.env
  const storage = JSON.parse(await readFile(candidate.path, 'utf8')) as Record<string, unknown>
  const appRoot = dirname(dirname(dirname(candidate.path)))
  const machineFile = nonEmpty(await readFile(join(appRoot, 'machineid'), 'utf8').catch(() => ''))
  const telemetryMachine = nonEmpty(storage['telemetry.machineId'])
  const devDevice = nonEmpty(storage['telemetry.devDeviceId'])
  const dcDevice = deviceCenterId(storage)
  // Historical official chat logs use the 64-char telemetry.machineId as
  // x-machine-id. The root machineid file remains a fallback only.
  const machineId = telemetryMachine ?? machineFile
  if (machineId === undefined) throw new Error(`Trae ${candidate.edition} has no stable machine identity`)
  // The numeric suffix of iCubeAuthInfo://icube-dc:<id> exactly matches the
  // x-device-id observed in official CN chat logs. Telemetry remains fallback.
  const deviceId = dcDevice ?? devDevice ?? createHash('sha256').update(machineId).digest('hex').slice(0, 32)
  const buildVersion = nonEmpty(storage['iCubeLastVersion'])
  // product.json holds the app version that the real client sends as
  // x-app-version / x-ide-version. Only CN/SOLO installs are targeted, and the
  // file lives under the app bundle on macOS but under LOCALAPPDATA\Programs on
  // Windows. Failures here must not break identity resolution, so each path is
  // tried in order and non-existent candidates are simply skipped.
  const appName = candidate.edition === 'cn' ? 'Trae CN' : candidate.edition === 'solo' ? 'TRAE SOLO CN' : undefined
  const productPaths: string[] = []
  if (appName !== undefined && (platform === 'darwin' || platform === 'win32')) {
    if (platform === 'darwin') {
      productPaths.push(join('/Applications', `${appName}.app`, 'Contents', 'Resources', 'app', 'product.json'))
    } else {
      const localRoots = [env.LOCALAPPDATA, join(home, 'AppData', 'Local')]
        .filter((value): value is string => typeof value === 'string' && value !== '')
        .filter((value, index, all) => all.indexOf(value) === index)
      for (const root of localRoots) {
        productPaths.push(join(root, 'Programs', appName, 'resources', 'app', 'product.json'))
      }
    }
  }
  let product: Record<string, unknown> = {}
  for (const path of productPaths) {
    try { product = JSON.parse(await readFile(path, 'utf8')) as Record<string, unknown>; break } catch {}
  }
  const appVersion = nonEmpty(product['appVersion'])
  const deviceBrand = platform === 'darwin' ? nonEmpty(env['TRAE_DEVICE_BRAND']) : undefined
  const deviceCpu = cpus()[0]?.model.split(' ')[0]
  const osVersion = `${platform === 'darwin' ? 'macOS' : platform === 'win32' ? 'Windows' : platform} ${release()}`
  return {
    edition: candidate.edition,
    machineId,
    deviceId,
    ...appVersion === undefined ? {} : { appVersion },
    ...buildVersion === undefined ? {} : { buildVersion },
    ...deviceBrand === undefined ? {} : { deviceBrand },
    ...deviceCpu === undefined ? {} : { deviceCpu },
    osVersion,
    platform,
  }
}

/** Detect a missing storage file (as opposed to a parse/identity error). */
function isFileMissing(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'code' in error && (error as { code?: unknown }).code === 'ENOENT'
}

/**
 * Try candidates in order and return the first that yields a valid identity;
 * fail hard only when none do. Mirrors the credential store's skip-missing
 * semantics so a machine with only SOLO (no CN install) resolves correctly
 * instead of pinning the first candidate and throwing on a missing file.
 * When every candidate is absent from disk the error names all tried paths;
 * a candidate that exists but fails to parse still surfaces its own error.
 */
export async function pickTraeStorageIdentity(
  candidates: readonly TraeStorageCandidate[],
  options: TraeIdentityReadOptions = {},
): Promise<TraeIdentity> {
  let lastError: unknown
  let anyPresent = false
  for (const candidate of candidates) {
    try {
      return await readTraeIdentity(candidate, options)
    } catch (error) {
      lastError = error
      if (!isFileMissing(error)) anyPresent = true
    }
  }
  const tried = candidates.map(item => item.path).join(' or ')
  if (!anyPresent) throw new Error(`Trae storage was not found (${tried})`)
  throw lastError instanceof Error ? lastError : new Error(`Trae identity could not be resolved (${tried})`)
}

/** Headers derived from actual persisted identity, never a new random identity per request. */
export function identityHeaders(identity: TraeIdentity): Record<string, string> {
  return {
    'x-machine-id': identity.machineId,
    'x-device-id': identity.deviceId,
    'x-device-type': identity.platform === 'darwin' ? 'mac' : identity.platform === 'win32' ? 'windows' : identity.platform,
    ...identity.deviceBrand === undefined ? {} : { 'x-device-brand': identity.deviceBrand },
    ...identity.deviceCpu === undefined ? {} : { 'x-device-cpu': identity.deviceCpu },
    ...identity.osVersion === undefined ? {} : { 'x-os-version': identity.osVersion },
    ...identity.appVersion === undefined ? {} : { 'x-app-version': identity.appVersion, 'x-ide-version': identity.appVersion },
    ...identity.buildVersion === undefined ? {} : { 'x-app-version-code': identity.buildVersion, 'x-ide-version-code': identity.buildVersion },
    'x-ide-version-type': 'stable',
  }
}
