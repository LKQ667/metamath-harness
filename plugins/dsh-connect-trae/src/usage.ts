import type { TraeCredential } from './auth.ts'

/**
 * Read-only Trae usage/credits client.
 *
 * Sources the verified `api.trae.cn` pay/ug endpoints (see
 * `docs/USAGE_API_RESEARCH.md`). All queries are read-only and do not consume
 * Trae credits. The per-session consumption detail table is deliberately not
 * included: the endpoint returns no rows for the current account, so we only
 * expose what is actually retrievable.
 */

export const TRAE_PAY_BASE = 'https://api.trae.cn'

export interface TraeUsageOptions {
  credential(): Promise<TraeCredential | undefined>
  fetchImpl?: typeof fetch
  baseUrl?: string
  timeoutMs?: number
}

export interface TraeUsageSummary {
  totalAmount: number
  consumedAmount: number
  consumptionRatio: number
}

export interface TraeUsagePack {
  displayDesc: string
  entitlementId: string
  endTimeMs: number
  currency: number
  /** 0 = non-Work/general endpoint, 1 = Work endpoint. */
  availableEndpoint?: number
  creditsLimit?: number
  /** Credits consumed from this pack (`usage.credits_amount`). */
  consumedCredits?: number
}

export interface TraeUsageSnapshot {
  isCreditsBilling: boolean
  isDollarUsageBilling: boolean
  isPayFreshman: boolean
  inTrial: boolean
  trialEndTimeMs: number
  summary: TraeUsageSummary
  packs: TraeUsagePack[]
}

export interface TraeCheckinStatus {
  checkedIn: boolean
  credits: number
  enabled: boolean
}

export interface TraeActivityRule {
  activityId: string
  enabled: boolean
  activityType: number
  startTimeMs: number
  endTimeMs: number
  workExtra?: Record<string, unknown>
}

export interface TraeUsageView {
  snapshot: TraeUsageSnapshot
  checkin: TraeCheckinStatus
  activities: TraeActivityRule[]
}

function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function parseUsageSnapshot(payload: Record<string, unknown>): TraeUsageSnapshot {
  const summaryRaw = payload['usage_summary'] as Record<string, unknown> | undefined
  const summary: TraeUsageSummary = {
    totalAmount: asNumber(summaryRaw?.['total_amount']) ?? 0,
    consumedAmount: asNumber(summaryRaw?.['consumed_amount']) ?? 0,
    consumptionRatio: asNumber(summaryRaw?.['consumption_ratio']) ?? 0,
  }
  const trial = payload['trial_status'] as Record<string, unknown> | undefined
  const packs: TraeUsagePack[] = []
  const rawPacks = Array.isArray(payload['user_entitlement_pack_list']) ? payload['user_entitlement_pack_list'] : []
  for (const raw of rawPacks) {
    if (typeof raw !== 'object' || raw === null) continue
    const pack = raw as Record<string, unknown>
    const base = pack['entitlement_base_info'] as Record<string, unknown> | undefined
    const quota = base?.['quota'] as Record<string, unknown> | undefined
    const usage = pack['usage'] as Record<string, unknown> | undefined
    const productExtra = base?.['product_extra'] as Record<string, unknown> | undefined
    const packageExtra = productExtra?.['package_extra'] as Record<string, unknown> | undefined
    const packageQuota = packageExtra?.['quota'] as Record<string, unknown> | undefined
    const creditsLimit = asNumber(packageQuota?.['credits_limit']) ?? asNumber(quota?.['credits_limit'])
    const consumedCredits = asNumber(usage?.['credits_amount'])
    const availableEndpoint = asNumber(base?.['available_endpoint'])
    packs.push({
      displayDesc: typeof pack['display_desc'] === 'string' ? pack['display_desc'] : '',
      entitlementId: typeof base?.['entitlement_id'] === 'string' ? base['entitlement_id'] : '',
      endTimeMs: asNumber(base?.['end_time']) ?? 0,
      currency: asNumber(base?.['currency']) ?? 0,
      ...availableEndpoint === undefined ? {} : { availableEndpoint },
      ...creditsLimit === undefined ? {} : { creditsLimit },
      ...consumedCredits === undefined ? {} : { consumedCredits },
    })
  }
  return {
    isCreditsBilling: payload['is_credits_billing'] === true,
    isDollarUsageBilling: payload['is_dollar_usage_billing'] === true,
    isPayFreshman: payload['is_pay_freshman'] === true,
    inTrial: trial?.['is_in_trial'] === true,
    trialEndTimeMs: asNumber(trial?.['trial_end_time']) ?? 0,
    summary,
    packs,
  }
}

/**
 * A read-only client for the verified Trae usage/credits endpoints.
 * All methods are safe to call from a plugin and never mutate account state.
 */
export class TraeUsageClient {
  private readonly fetchImpl: typeof fetch
  private readonly baseUrl: string
  private readonly timeoutMs: number

  constructor(private readonly options: TraeUsageOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch
    this.baseUrl = options.baseUrl ?? TRAE_PAY_BASE
    this.timeoutMs = options.timeoutMs ?? 30_000
  }

  private async authedHeaders(): Promise<Record<string, string>> {
    const credential = await this.options.credential()
    if (credential === undefined || credential.accessToken === '') {
      throw new Error('Trae credential is not available; cannot query usage')
    }
    return {
      'Authorization': `Cloud-IDE-JWT ${credential.accessToken}`,
      'Content-Type': 'application/json',
      'User-Agent': 'Mozilla/5.0',
      'Origin': 'https://www.trae.cn',
      'Referer': 'https://www.trae.cn/',
    }
  }

  private async post<T>(path: string, data: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
    const headers = await this.authedHeaders()
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal: signal ?? AbortSignal.timeout(this.timeoutMs),
    })
    if (!response.ok) throw new Error(`Trae usage endpoint ${path} returned HTTP ${response.status}`)
    return await response.json() as T
  }

  /** Total entitlements / credits and per-pack breakdown. */
  async snapshot(signal?: AbortSignal): Promise<TraeUsageSnapshot> {
    const payload = await this.post<Record<string, unknown>>('/trae/api/v2/pay/web_user_ent_usage', { require_usage: true }, signal)
    return parseUsageSnapshot(payload)
  }

  /** Daily check-in status. */
  async checkinStatus(signal?: AbortSignal): Promise<TraeCheckinStatus> {
    const payload = await this.post<Record<string, unknown>>('/trae/api/v2/ug/checkin_credits/status', {}, signal)
    return {
      checkedIn: payload['checked_in'] === true,
      credits: asNumber(payload['credits']) ?? 0,
      enabled: payload['enable'] !== false,
    }
  }

  /** Rewards / activity rules. */
  async activities(signal?: AbortSignal): Promise<TraeActivityRule[]> {
    const payload = await this.post<Record<string, unknown>>('/trae/api/v2/ug/activity/info', {}, signal)
    const rawActivities = Array.isArray(payload['commercial_activities']) ? payload['commercial_activities'] : []
    const activities: TraeActivityRule[] = []
    for (const raw of rawActivities) {
      if (typeof raw !== 'object' || raw === null) continue
      const rule = raw as Record<string, unknown>
      activities.push({
        activityId: typeof rule['activity_id'] === 'string' ? rule['activity_id'] : '',
        enabled: rule['Enabled'] === true,
        activityType: asNumber(rule['activity_type']) ?? 0,
        startTimeMs: asNumber(rule['start_time_ms']) ?? 0,
        endTimeMs: asNumber(rule['end_time_ms']) ?? 0,
        ...rule['work_extra'] === undefined ? {} : { workExtra: rule['work_extra'] as Record<string, unknown> },
      })
    }
    return activities
  }

  /** Convenience: snapshot + check-in + activities in one call (best-effort, non-fatal on missing). */
  async view(signal?: AbortSignal): Promise<TraeUsageView> {
    const [snapshot, checkin, activities] = await Promise.all([
      this.snapshot(signal),
      this.checkinStatus(signal),
      this.activities(signal),
    ])
    return { snapshot, checkin, activities }
  }
}
