/**
 * Trae usage card contributed to Harness Plugin configuration.
 *
 * Structure, CSS classes, and button primitives mirror `dsh-subagent-default-model`'s
 * `SubagentModelCard` so the two plugins share one external-presentation language.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { createElement as h } from 'react'
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-settings-plugins/client'
import { IconChevronDownOutline14 } from '@deepseek-ai/dsh-client-ui-primitives'
import { TRAE_ACCOUNTS_REFRESH_PATH, TRAE_MODELS_REFRESH_PATH, TRAE_USAGE_PATH } from '../status-paths.ts'
import type { TraeWebModel, TraeWebUsage } from '../status-paths.ts'
import { TRAE_PLUGIN_ICON } from './icon.ts'
import { TRAE_CARD_CSS } from './styles.ts'
import type { TraeSettingsKey } from './locales.ts'

/** Localized copy injected by the browser-plugin registration. */
export interface TraeUsageCardInjected {
  t: (key: TraeSettingsKey, params?: Record<string, unknown>) => string
  settingsScope: {
    getSnapshot(): { status: string; value?: unknown; writable: boolean }
    subscribe(listener: () => void): () => void
    set(field: string, value: unknown): Promise<void>
  }
}

/** Props delivered by the Plugin configuration item slot. */
export type TraeUsageCardProps =
  PropsRuntime<'settings.plugin.item'>
  & Partial<TraeUsageCardInjected>

const POLL_INTERVAL_MS = 60_000
const TRAE_GITHUB_URL = 'https://github.com/dingminhua/dsh-connect-trae'

/** Inject the shared card CSS once. */
if (typeof document !== 'undefined') {
  const cssId = 'dsh-connect-trae/client.css'
  if (!document.querySelector(`style[data-plugin-css="${cssId}"]`)) {
    const styleTag = document.createElement('style')
    styleTag.dataset.plugin = 'dsh-connect-trae'
    styleTag.dataset.pluginCss = cssId
    styleTag.textContent = TRAE_CARD_CSS
    document.head.appendChild(styleTag)
  }
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatDateTime(value: number): string {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function formatCapacity(value: number | undefined, unknown: string): string {
  if (value === undefined) return unknown
  if (value >= 1_000_000 && value % 1_000_000 === 0) return `${value / 1_000_000}M`
  if (value >= 1_000 && value % 1_000 === 0) return `${value / 1_000}K`
  return formatNumber(value)
}

function dotStyle(status: TraeWebUsage['status']): Record<string, string> {
  const color = status === 'signed-in'
    ? 'var(--dsw-alias-state-success-primary, #22a06b)'
    : status === 'error'
      ? 'var(--dsw-alias-state-error-primary, #d92d20)'
      : 'var(--dsw-alias-label-dimmed, #9aa0a6)'
  return { background: color }
}

/** Render Trae sign-in state and the total usage summary as one expandable card. */
export function TraeUsageCard({ t, settingsScope }: TraeUsageCardProps) {
  if (t === undefined) throw new Error('Trae usage card requires its translation function')
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<TraeWebUsage>({ status: 'signed-out', accounts: [] })
  const [busy, setBusy] = useState(false)
  const [settingsRevision, setSettingsRevision] = useState(0)
  const [draftModels, setDraftModels] = useState<TraeWebModel[] | undefined>(undefined)
  const [draftEnabledIds, setDraftEnabledIds] = useState<Set<string> | undefined>(undefined)
  const [draftImageIds, setDraftImageIds] = useState<Set<string> | undefined>(undefined)
  const [draftContextBudgets, setDraftContextBudgets] = useState<Record<string, number> | undefined>(undefined)
  const [saving, setSaving] = useState(false)
  const [switchingAccount, setSwitchingAccount] = useState(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => settingsScope?.subscribe(() => { setSettingsRevision(value => value + 1) }), [settingsScope])

  const refreshUsage = useCallback(async (signal?: AbortSignal): Promise<TraeWebUsage | undefined> => {
    try {
      const response = await fetch(TRAE_USAGE_PATH, {
        headers: { accept: 'application/json' },
        credentials: 'same-origin',
        ...signal === undefined ? {} : { signal },
      })
      const value: unknown = await response.json().catch(() => undefined)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      if (mounted.current && signal?.aborted !== true) setStatus(value as TraeWebUsage)
      return value as TraeWebUsage
    } catch (error: unknown) {
      if (mounted.current && signal?.aborted !== true) {
        setStatus({ status: 'error', message: error instanceof Error ? error.message : t('row.requestFailed') })
      }
      return undefined
    }
  }, [t])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    void refreshUsage(controller.signal)
    return () => { controller.abort() }
  }, [open, refreshUsage])

  useEffect(() => {
    if (!open || status.status !== 'signed-in') return
    const controller = new AbortController()
    const timer = window.setInterval(() => { void refreshUsage(controller.signal) }, POLL_INTERVAL_MS)
    return () => {
      window.clearInterval(timer)
      controller.abort()
    }
  }, [open, refreshUsage, status.status])

  const rescanAccounts = async (): Promise<void> => {
    setBusy(true)
    try {
      const response = await fetch(TRAE_ACCOUNTS_REFRESH_PATH, {
        method: 'POST', headers: { accept: 'application/json' }, credentials: 'same-origin',
      })
      const body = await response.json() as { accounts?: { id: string; selected: boolean }[] }
      if (!response.ok || !Array.isArray(body.accounts)) throw new Error(`HTTP ${response.status}`)
      const selected = body.accounts.find(account => account.selected)?.id
      const configured = settingsScope?.getSnapshot().value
      const configuredId = typeof configured === 'object' && configured !== null && typeof (configured as { accountId?: unknown }).accountId === 'string'
        ? (configured as { accountId: string }).accountId
        : undefined
      if (selected !== undefined && selected !== configuredId && settingsScope?.getSnapshot().writable === true) {
        await settingsScope.set('accountId', selected)
      }
      await refreshUsage()
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const switchAccount = async (accountId: string): Promise<void> => {
    if (settingsScope === undefined) return
    setSwitchingAccount(true)
    try {
      await settingsScope.set('accountId', accountId)
      await refreshUsage()
    } finally {
      if (mounted.current) setSwitchingAccount(false)
    }
  }

  const refreshModels = async (): Promise<void> => {
    setBusy(true)
    try {
      const response = await fetch(TRAE_MODELS_REFRESH_PATH, {
        method: 'POST',
        headers: { accept: 'application/json' },
        credentials: 'same-origin',
      })
      const body = await response.json() as { models?: TraeWebModel[] }
      if (!response.ok || !Array.isArray(body.models)) throw new Error(`HTTP ${response.status}`)
      const fresh = body.models
      const freshIds = new Set(fresh.map(model => model.id))
      // Re-map the user's CURRENT selections (draft first, then saved) onto the
      // fresh catalog by model id, so refresh never silently loses enabled
      // choices, image opt-ins, or context budgets.
      const stillEnabled = [...activeEnabledIds].filter(id => freshIds.has(id))
      const stillImages = [...activeImageIds].filter(id => freshIds.has(id))
      const stillBudgets: Record<string, number> = {}
      for (const id of freshIds) {
        const budget = activeContextBudgets[id]
        if (typeof budget === 'number') stillBudgets[id] = budget
      }
      setDraftModels(fresh.map(model => ({ ...model, input: ['text'] })))
      setDraftEnabledIds(new Set(stillEnabled))
      setDraftImageIds(new Set(stillImages))
      setDraftContextBudgets(stillBudgets)
    } catch (error: unknown) {
      if (mounted.current) setStatus({ status: 'error', message: error instanceof Error ? error.message : t('row.requestFailed') })
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const settingsValue = settingsScope?.getSnapshot().value
  const savedContextBudgets = typeof settingsValue === 'object' && settingsValue !== null && typeof (settingsValue as { contextBudgets?: unknown }).contextBudgets === 'object' && (settingsValue as { contextBudgets?: unknown }).contextBudgets !== null
    ? (settingsValue as { contextBudgets: Record<string, number> }).contextBudgets
    : {}
  const savedImageIds = new Set(
    typeof settingsValue === 'object' && settingsValue !== null && Array.isArray((settingsValue as { imageModelIds?: unknown }).imageModelIds)
      ? (settingsValue as { imageModelIds: unknown[] }).imageModelIds.filter((id): id is string => typeof id === 'string')
      : [],
  )
  void settingsRevision
  // The card always renders the last-refreshed raw directory (`status.models`
  // carries `lastCatalog`), never a stale saved snapshot. Enabled flags come
  // from the user's stored selection, re-mapped onto the current catalog by
  // model id (= Trae name); context budgets work the same way.
  const visibleModels = draftModels ?? (status.status === 'signed-in' ? status.models : [])
  const savedEnabledIds = status.status === 'signed-in' ? new Set(status.enabledModelIds) : new Set<string>()
  const activeEnabledIds = draftEnabledIds ?? savedEnabledIds
  const activeImageIds = draftImageIds ?? savedImageIds
  const activeContextBudgets = draftContextBudgets ?? savedContextBudgets
  const dirty = draftModels !== undefined || draftEnabledIds !== undefined || draftImageIds !== undefined || draftContextBudgets !== undefined

  const toggleModel = (modelId: string): void => {
    const next = new Set(activeEnabledIds)
    if (!next.delete(modelId)) next.add(modelId)
    setDraftEnabledIds(next)
    setDraftModels([...visibleModels])
  }

  const toggleImage = (modelId: string): void => {
    const next = new Set(activeImageIds)
    if (!next.delete(modelId)) next.add(modelId)
    setDraftImageIds(next)
    setDraftModels([...visibleModels])
  }

  const setContextBudget = (modelId: string, budget: number | undefined): void => {
    const next = { ...activeContextBudgets }
    if (budget === undefined) delete next[modelId]
    else next[modelId] = budget
    setDraftContextBudgets(next)
    setDraftModels([...visibleModels])
  }

  const discardModels = (): void => {
    setDraftModels(undefined)
    setDraftEnabledIds(undefined)
    setDraftImageIds(undefined)
    setDraftContextBudgets(undefined)
  }

  const saveModels = async (): Promise<void> => {
    if (settingsScope === undefined) return
    setSaving(true)
    try {
      // Save the raw directory plus the pure selection and budgets. The Host
      // derives the runtime catalog from these on save/restart, so re-opening
      // the card re-reads Trae's current catalog instead of a stale snapshot.
      await settingsScope.set('lastCatalog', visibleModels.map(model => ({ ...model, input: ['text'] })))
      await settingsScope.set('enabledModelIds', [...activeEnabledIds])
      await settingsScope.set('imageModelIds', [...activeImageIds].filter(id => activeEnabledIds.has(id)))
      await settingsScope.set('contextBudgets', activeContextBudgets)
      discardModels()
      await refreshUsage()
    } finally {
      if (mounted.current) setSaving(false)
    }
  }

  const title = t('row.title')
  const label = status.status === 'signed-in'
    ? t('row.signedIn', { accountName: status.accountName })
    : status.status === 'error'
      ? t('row.requestFailed')
      : t('row.signedOut')

  return (
    <li className={`dsm-plugin-card${open ? ' dsm-plugin-card-open' : ''}`}>
      <button
        type="button"
        className="dsm-plugin-card-header"
        aria-expanded={open}
        aria-label={`${t(open ? 'row.collapse' : 'row.expand')}: ${title}`}
        onClick={() => { setOpen(!open) }}
      >
        <img className="dsm-plugin-card-icon" src={TRAE_PLUGIN_ICON} alt="" />
        <span className="dsm-plugin-card-head">
          <span className="dsm-plugin-card-title">{title}</span>
          <span className="dsm-plugin-card-description">{t('row.desc')}</span>
        </span>
        <span
          aria-hidden="true"
          className={`dsm-plugin-card-chevron${open ? ' dsm-plugin-card-chevron-open' : ''}`}
        >
          {h(IconChevronDownOutline14, { size: 14 })}
        </span>
      </button>
      <div className="dsm-plugin-card-body" hidden={!open}>
        {open
          ? <div className="dsm-trae-usage">
              <div className="dsm-trae-usage-account">
                <div className="dsm-trae-usage-account-copy" role="status">
                  <div className="dsm-trae-usage-status">
                    <span aria-hidden="true" className="dsm-trae-usage-dot" style={dotStyle(status.status)} />
                    <span>{label}</span>
                  </div>
                  {status.status === 'signed-in'
                    ? <span className="dsm-trae-usage-expiry">
                        {t('row.tokenExpiry', { expiresAt: formatDateTime(status.tokenExpiresAtMs) })}
                      </span>
                    : null}
                </div>
                <button
                  type="button"
                  className="dsm-btn dsm-btn-outline"
                  disabled={busy}
                  onClick={() => { void rescanAccounts() }}
                >
                  {busy ? t('row.accountsScanning') : t('row.refreshTokens')}
                </button>
              </div>
              {status.status !== 'error' && status.accounts.length > 0
                ? <section className="dsm-trae-account-picker" aria-label={t('row.accountsTitle')}>
                    <div className="dsm-trae-usage-select-wrap">
                      <select
                        className="dsm-trae-usage-select"
                        value={status.status === 'signed-in' ? status.accountId : ''}
                        disabled={switchingAccount || settingsScope?.getSnapshot().writable !== true}
                        onChange={event => { void switchAccount(event.currentTarget.value) }}
                      >
                        {status.accounts.map(account => <option key={account.id} value={account.id}>{account.accountName} · {account.edition}</option>)}
                      </select>
                    </div>
                  </section>
                : null}
              {status.status === 'signed-in'
                ? <>
                    {status.credits === undefined ? null : (
                      <div className="dsm-trae-usage-list">
                        <div className="dsm-trae-usage-stats dsm-trae-usage-stats-two">
                          <div className="dsm-trae-usage-stat dsm-trae-usage-stat-work">
                            <div className="dsm-trae-usage-stat-head">
                              <span className="dsm-trae-usage-stat-label">{t('row.workCreditsLabel')}</span>
                              <span className="dsm-trae-usage-stat-badge dsm-trae-usage-stat-badge-off">{t('row.workNotUsable')}</span>
                            </div>
                            <span className="dsm-trae-usage-stat-value dsm-trae-usage-stat-value-work">{formatNumber(status.credits.workAvailable)}</span>
                            <span className="dsm-trae-usage-stat-hint">{t('row.workUsableHint')}</span>
                          </div>
                          <div className="dsm-trae-usage-stat dsm-trae-usage-stat-general">
                            <div className="dsm-trae-usage-stat-head">
                              <span className="dsm-trae-usage-stat-label">{t('row.generalCreditsLabel')}</span>
                              <span className="dsm-trae-usage-stat-badge dsm-trae-usage-stat-badge-on">{t('row.generalUsable')}</span>
                            </div>
                            <span className="dsm-trae-usage-stat-value dsm-trae-usage-stat-value-general">{formatNumber(status.credits.generalAvailable)}</span>
                            <span className="dsm-trae-usage-stat-hint">{t('row.generalUsableHint')}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {status.creditsError === undefined ? null
                      : <p className="dsm-trae-usage-error">{t('row.creditsError', { message: status.creditsError })}</p>}
                    <section className="dsm-trae-models" aria-label={t('row.modelsTitle')}>
                      <div className="dsm-trae-models-head">
                        <div>
                          <h3 className="dsm-trae-models-title">{t('row.modelsTitle')}</h3>
                          <p className="dsm-trae-models-summary">{t('row.modelsSummary', { count: activeEnabledIds.size })}</p>
                        </div>
                        <button
                          type="button"
                          className="dsm-btn dsm-btn-outline"
                          disabled={busy}
                          onClick={() => { void refreshModels() }}
                        >
                          {busy ? t('row.modelsRefreshing') : t('row.modelsRefresh')}
                        </button>
                      </div>
                      <div className="dsm-trae-model-list">
                        {visibleModels.map(model => (
                          <div className={`dsm-trae-model${activeEnabledIds.has(model.id) ? '' : ' dsm-trae-model-disabled'}`} key={model.id}>
                            <div className="dsm-trae-model-head">
                              <label className="dsm-trae-model-enabled">
                                <input
                                  type="checkbox"
                                  checked={activeEnabledIds.has(model.id)}
                                  disabled={settingsScope?.getSnapshot().writable !== true || saving}
                                  onChange={() => { toggleModel(model.id) }}
                                />
                                <span className="dsm-trae-model-copy">
                                  <span className="dsm-trae-model-name">
                                    {model.name}
                                    {model.creditMultiplier === undefined ? null
                                      : <span className="dsm-trae-model-name-rate">({model.creditMultiplier.toFixed(2)}x)</span>}
                                  </span>
                                </span>
                              </label>
                              <div className="dsm-trae-model-options">
                                <label className="dsm-trae-model-image">
                                  <input
                                    type="checkbox"
                                    checked={activeImageIds.has(model.id)}
                                    disabled={settingsScope?.getSnapshot().writable !== true || saving}
                                    onChange={() => { toggleImage(model.id) }}
                                  />
                                  <span>{t('row.modelImage')}</span>
                                </label>
                              <fieldset className="dsm-trae-context-budget" aria-label={t('row.contextBudget')}>
                                {model.maxContextWindow !== undefined
                                  ? <label>
                                      <input
                                        type="radio"
                                        name={`context-${model.id}`}
                                        checked={activeContextBudgets[model.id] !== model.maxContextWindow}
                                        disabled={settingsScope?.getSnapshot().writable !== true || saving}
                                        onChange={() => { setContextBudget(model.id, model.contextWindow) }}
                                      />
                                      <span>{formatCapacity(model.contextWindow, t('row.modelUnknown'))}</span>
                                    </label>
                                  : null}
                                <label>
                                  <input
                                    type="radio"
                                    name={`context-${model.id}`}
                                    checked={model.maxContextWindow === undefined || activeContextBudgets[model.id] === model.maxContextWindow}
                                    disabled={model.maxContextWindow === undefined || settingsScope?.getSnapshot().writable !== true || saving}
                                    onChange={() => { setContextBudget(model.id, model.maxContextWindow) }}
                                  />
                                  <span>{formatCapacity(model.maxContextWindow ?? model.contextWindow, t('row.modelUnknown'))}</span>
                                </label>
                              </fieldset>
                              </div>
                            </div>
                            <div className="dsm-trae-model-meta">
                              <span>{t('row.modelContext', { context: formatCapacity(model.maxContextWindow ?? model.contextWindow, t('row.modelUnknown')) })}</span>
                              {model.maxTokens === undefined ? null
                                : <span>{t('row.modelOutput', { output: formatCapacity(model.maxTokens, t('row.modelUnknown')) })}</span>}
                              {model.reasoning === undefined ? null
                                : <span>{t('row.modelReasoning', { efforts: model.reasoning.supported.join(' / ') })}</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                      <p className="dsm-trae-model-capability-note">{t('row.modelCapabilityPending')}</p>
                      <div className="dsm-trae-model-actions">
                        <a
                          className="dsm-trae-usage-cheer"
                          href={TRAE_GITHUB_URL}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {t('row.cheer')}
                          <span className="dsm-trae-usage-cheer-star" aria-hidden="true">★</span>
                        </a>
                        <div className="dsm-trae-model-actions-buttons">
                          <button type="button" className="dsm-btn dsm-btn-outline" disabled={!dirty || saving} onClick={discardModels}>
                            {t('row.discard')}
                          </button>
                          <button type="button" className="dsm-btn dsm-btn-primary" disabled={!dirty || saving || activeEnabledIds.size === 0} onClick={() => { void saveModels() }}>
                            {saving ? t('row.saving') : t('row.save')}
                          </button>
                        </div>
                      </div>
                    </section>
                  </>
                : null}
              {status.status === 'signed-out' ? <p className="dsm-trae-usage-text">{status.message ?? t('row.signedOutHint')}</p> : null}
              {status.status === 'error' ? <p className="dsm-trae-usage-error">{status.message}</p> : null}
            </div>
          : null}
      </div>
    </li>
  )
}
