import type { QoderAccountInfo } from '../qoder/account.ts'
import type { QoderCatalogModel } from '../qoder/catalog.ts'
import type { QoderRegion } from '../qoder/region.ts'
import type { QoderWebSearchMode } from '../dsh/config.ts'
import type { QoderRpcResult } from '../dsh/rpc-channel.ts'
import type { QoderCredentialCopy } from './locales.ts'

export interface QoderCredentialOperations {
  describe(): Promise<QoderCredentialStatus | undefined>
  store(value: string): Promise<boolean>
  remove(): Promise<boolean>
  getAccount(force?: boolean): Promise<QoderAccountResult | undefined>
  getModelSnapshot(): QoderModelSettingsSnapshot
  subscribeModels(listener: () => void): () => void
  storeModels(region: QoderRegion, models: QoderCatalogModel[]): Promise<boolean>
  storeRegion(region: QoderRegion): Promise<boolean>
  storeWebSearchMode(mode: QoderWebSearchMode): Promise<boolean>
  discoverModels(): Promise<QoderModelDiscoveryResult>
  subscribe(listener: () => void): () => void
}

export interface QoderModelSettingsSection {
  region?: QoderRegion
  modelsByRegion?: Partial<Record<QoderRegion, QoderCatalogModel[]>>
  /** @deprecated Migrated to modelsByRegion. */
  models?: QoderCatalogModel[]
  webSearchMode?: QoderWebSearchMode
}


export interface QoderModelSettingsSnapshot {
  status: 'loading' | 'ready' | 'unavailable'
  value: QoderModelSettingsSection | undefined
  base: unknown
  user: unknown
  revision: number | undefined
  writable: boolean
  mode: 'host' | 'memory'
}

export type QoderModelDiscoveryResult = QoderRpcResult<QoderCatalogModel[]>

export interface QoderModelReconciliation {
  catalog: QoderCatalogModel[]
  selected: QoderCatalogModel[]
  unavailableIds: Set<string>
}

export function reconcileQoderModels(
  known: readonly QoderCatalogModel[],
  discovered: readonly QoderCatalogModel[],
): QoderModelReconciliation {
  const availableIds = new Set(discovered.map(model => model.id))
  const unavailable = known.filter(model => !availableIds.has(model.id))
  const previous = new Map(known.map(model => [model.id, model]))
  const reconciled = discovered.map(model => {
    const budget = previous.get(model.id)?.contextWindow
    return budget === undefined || model.contextWindow === undefined
      ? model
      : { ...model, contextWindow: Math.min(budget, model.contextWindow) }
  })
  return {
    catalog: [...reconciled, ...unavailable],
    selected: reconciled,
    unavailableIds: new Set(unavailable.map(model => model.id)),
  }
}

export interface QoderCredentialStatus {
  configured: boolean
  source?: string
  writable: boolean
}

export type QoderAccountResult = QoderRpcResult<QoderAccountInfo>

export interface QoderCredentialInjected {
  operations: QoderCredentialOperations
  t(key: QoderCredentialCopy, values?: Record<string, string | number>): string
  /**
   * Read the active UI locale at render time so a language switch is reflected
   * immediately; never snapshot it once during plugin setup.
   */
  activeLocale(): string
}
