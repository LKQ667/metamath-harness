import type { TraeCredential } from './auth.ts'
import { parseTraeRemoteModel, type TraeDiscoveredModel } from './model-metadata.ts'

export const TRAE_SOLO_REMOTE_BASE = 'https://solo.trae.cn/api/remote/v1'

export interface TraeSoloRemoteCatalogOptions {
  credential(): Promise<TraeCredential>
  fetchImpl?: typeof fetch
  baseUrl?: string
}

/**
 * Read-only model catalog client for the SOLO Web API.
 *
 * This deliberately has no chat/session method: the Remote session protocol
 * only exposes a final answer and cannot preserve DSH's structured tool loop.
 */
export class TraeSoloRemoteCatalogClient {
  private readonly fetchImpl: typeof fetch
  private readonly baseUrl: string

  constructor(private readonly options: TraeSoloRemoteCatalogOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch
    this.baseUrl = options.baseUrl ?? TRAE_SOLO_REMOTE_BASE
  }

  private async headers(): Promise<Record<string, string>> {
    const credential = await this.options.credential()
    return {
      'Authorization': `Cloud-IDE-JWT ${credential.accessToken}`,
      'Content-Type': 'application/json',
      'x-trae-client-type': 'web',
      'x-trae-user-timezone': 'Asia/Shanghai',
      'x-preferenced-language': 'zh-cn',
      'Referer': 'https://solo.trae.cn/',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
  }

  async fetchModels(signal?: AbortSignal): Promise<TraeDiscoveredModel[]> {
    const headers = await this.headers()
    const response = await this.fetchImpl(`${this.baseUrl}/models?functions=solo_agent_remote,solo_work_remote`, { headers, signal: signal ?? AbortSignal.timeout(30_000) })
    if (!response.ok) throw new Error(`SOLO remote models returned HTTP ${response.status}`)
    const json = await response.json() as { code?: number; data?: { list?: { function?: string; models?: unknown[] }[] } }
    const groups = json.data?.list ?? []
    const preferred = groups.find(group => group.function === 'solo_agent_remote') ?? groups[0]
    const seen = new Set<string>()
    const models: TraeDiscoveredModel[] = []
    for (const raw of preferred?.models ?? []) {
      const model = parseTraeRemoteModel(raw)
      if (model === undefined || seen.has(model.id)) continue
      seen.add(model.id)
      models.push(model)
    }
    if (models.length === 0) throw new Error('SOLO remote models response contained no models')
    return models
  }
}
