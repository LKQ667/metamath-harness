import { homedir } from 'node:os'
import { join } from 'node:path'

export type TraeEdition = 'cn' | 'sg' | 'solo' | 'solo-sg'

export interface TraeStorageCandidate {
  edition: TraeEdition
  path: string
}

const APP_NAMES: Readonly<Record<TraeEdition, string>> = {
  cn: 'Trae CN',
  sg: 'Trae',
  solo: 'TRAE SOLO CN',
  'solo-sg': 'TRAE SOLO',
}

export function traeStorageCandidates(
  platform: NodeJS.Platform = process.platform,
  home: string = homedir(),
  env: NodeJS.ProcessEnv = process.env,
): TraeStorageCandidate[] {
  const result: TraeStorageCandidate[] = []
  for (const edition of ['cn', 'sg', 'solo', 'solo-sg'] as const) {
    const app = APP_NAMES[edition]
    let roots: string[]
    if (platform === 'darwin') roots = [join(home, 'Library', 'Application Support')]
    else if (platform === 'win32') {
      roots = [env.APPDATA, join(home, 'AppData', 'Roaming')].filter((value, index, all): value is string =>
        typeof value === 'string' && value !== '' && all.indexOf(value) === index)
    } else if (platform === 'linux') roots = [env.XDG_CONFIG_HOME || join(home, '.config')]
    else roots = []
    for (const root of roots) {
      result.push({ edition, path: join(root, app, 'User', 'globalStorage', 'storage.json') })
    }
  }
  return result
}
