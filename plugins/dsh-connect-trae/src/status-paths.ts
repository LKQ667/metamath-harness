/**
 * Node-free constants and types shared by the Host and browser halves.
 * Mirrors the `dsh-workbuddy-connect` status-route pattern so the plugin card
 * stays consistent with that project's external presentation.
 */

/** Plugin-owned usage endpoint consumed by its browser half. */
export const TRAE_USAGE_PATH = '/plugins/dsh-connect-trae/usage'
/** Plugin-owned live model refresh endpoint. */
export const TRAE_MODELS_REFRESH_PATH = '/plugins/dsh-connect-trae/models/refresh'
/** Plugin-owned local account rescan endpoint. */
export const TRAE_ACCOUNTS_REFRESH_PATH = '/plugins/dsh-connect-trae/accounts/refresh'

/** One credit pack and its remaining credit. */
export interface TraeWebCreditAccount {
  displayDesc: string
  remain: number
  size: number
}

/** Aggregated usage/credit answer rendered by the plugin card. */
export interface TraeWebCredits {
  total: number
  consumed: number
  available: number
  workAvailable: number
  generalAvailable: number
  accounts: readonly TraeWebCreditAccount[]
}

/** Editable Trae model row rendered by the plugin-owned settings card. */
export interface TraeWebModel {
  id: string
  name: string
  contextWindow?: number
  maxTokens?: number
  input?: ('text' | 'image')[]
  creditMultiplier?: number
  reasoningSupported?: boolean
  reasoning?: {
    supported: string[]
    defaultEffort?: string
  }
  maxContextWindow?: number
}

/** Daily check-in status rendered by the card. */
export interface TraeWebCheckin {
  checkedIn: boolean
  credits: number
}

/** One reward activity rule (name + work/general credits when present). */
export interface TraeWebActivity {
  activityId: string
  enabled: boolean
  workCredits?: number
  generalCredits?: number
}

export interface TraeWebAccount {
  id: string
  accountName: string
  edition: 'cn' | 'sg' | 'solo' | 'solo-sg'
  source: 'desktop' | 'dsh'
  tokenExpiresAtMs: number
  selected: boolean
}

/** The JSON document the plugin card renders. */
export type TraeWebUsage =
  | { status: 'signed-out'; accounts: readonly TraeWebAccount[]; message?: string }
  | {
    status: 'signed-in'
    accountId: string
    accountName: string
    tokenExpiresAtMs: number
    accounts: readonly TraeWebAccount[]
    models: readonly TraeWebModel[]
    enabledModelIds: readonly string[]
    rawChat?: {
      state: 'disabled' | 'unchecked' | 'available' | 'protocol-gated' | 'authentication' | 'credit' | 'rate' | 'transport' | 'server'
      checkedAtMs?: number
      status?: number
    }
    credits?: TraeWebCredits
    creditsError?: string
  }
  | { status: 'error'; message: string }
