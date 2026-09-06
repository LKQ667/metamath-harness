import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { join } from 'node:path'
import { homedir } from 'node:os'

const execFileAsync = promisify(execFile)

export interface TraeCachedModelConfig {
  name: string
  customConfig?: Record<string, unknown>
  promptMaxTokens?: number
  maxTokens?: number
  maxTurn?: number
  multimodal?: boolean
  modelType?: string
}

function positive(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}

/** Parse a safe subset of one cached model entry; credentials and endpoints are intentionally omitted. */
export function parseTraeCachedModel(value: unknown): TraeCachedModelConfig | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
  const raw = value as Record<string, unknown>
  if (typeof raw['name'] !== 'string' || raw['name'] === '') return undefined
  let customConfig: Record<string, unknown> | undefined
  if (typeof raw['custom_config'] === 'string' && raw['custom_config'] !== '') {
    try {
      const parsed = JSON.parse(raw['custom_config']) as unknown
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) customConfig = parsed as Record<string, unknown>
    } catch {}
  }
  const promptMaxTokens = positive(raw['prompt_max_tokens'])
  const maxTokens = positive(raw['max_tokens'])
  const maxTurn = positive(raw['max_turn'])
  return {
    name: raw['name'],
    ...customConfig === undefined ? {} : { customConfig },
    ...promptMaxTokens === undefined ? {} : { promptMaxTokens },
    ...maxTokens === undefined ? {} : { maxTokens },
    ...maxTurn === undefined ? {} : { maxTurn },
    ...typeof raw['multimodal'] === 'boolean' ? { multimodal: raw['multimodal'] } : {},
    ...typeof raw['model_type'] === 'string' ? { modelType: raw['model_type'] } : {},
  }
}

export interface TraeCachedModelReadOptions {
  /** Platform override for testing; defaults to process.platform. */
  platform?: NodeJS.Platform
  /** Home-directory override for testing; defaults to homedir(). */
  home?: string
  /** Environment override for testing; defaults to process.env. */
  env?: NodeJS.ProcessEnv
}

/**
 * Read Trae's own current user's model map via sqlite3 without exposing
 * secrets. The sqlite3 command line is a macOS prerequisite; on Windows it is
 * typically absent, so the call fails and callers fall back gracefully.
 */
export async function readTraeCachedModel(
  functionName: string,
  modelName: string,
  userId: string,
  options: TraeCachedModelReadOptions = {},
): Promise<TraeCachedModelConfig | undefined> {
  const platform = options.platform ?? process.platform
  const home = options.home ?? homedir()
  const env = options.env ?? process.env
  const database = platform === 'win32'
    ? join(env.APPDATA ?? join(home, 'AppData', 'Roaming'), 'Trae CN', 'User', 'globalStorage', 'state.vscdb')
    : join(home, 'Library', 'Application Support', 'Trae CN', 'User', 'globalStorage', 'state.vscdb')
  const key = `${userId}_AI.agent.model.model_list_map`
  const sql = `select value from ItemTable where key=${JSON.stringify(key)} limit 1;`
  const { stdout } = await execFileAsync('sqlite3', [database, sql], { maxBuffer: 8 * 1024 * 1024 })
  const document = JSON.parse(stdout) as Record<string, unknown>
  const list = Array.isArray(document[functionName]) ? document[functionName] as unknown[] : []
  return parseTraeCachedModel(list.find(item => typeof item === 'object' && item !== null && (item as { name?: unknown }).name === modelName))
}
