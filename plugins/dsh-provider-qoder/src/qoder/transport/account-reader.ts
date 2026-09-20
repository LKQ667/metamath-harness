/** Qoder subscriber profile and quota usage querying. */

import type { QoderAuthService } from './auth.ts'
import {
  getQoderUsageUrl,
  getQoderUserPlanUrl,
  getQoderUserStatusUrl,
  type QoderRegion,
} from './endpoints.ts'
import type {
  QoderAccountInfo,
  QoderLocalizedText,
  QoderQuota,
  QoderQuotaUsage,
  QoderResourcePackage,
  QoderSubscriberFeatureAllowed,
  QoderSubscriberOrganization,
  QoderSubscriberPlan,
  QoderSubscriberProfile,
  QoderSubscriberStatus,
} from '../account.ts'
import { QoderLlmError } from '../errors.ts'
import type { QoderLogger } from './logging.ts'
import {
  opaqueCredentialKey,
  openApiJsonRequest,
  retryMetadataRead,
  SingleFlight,
} from './request.ts'

const defaultUsageTtlMs = 60_000
const defaultUsageTimeoutMs = 15_000

export interface QoderUsageReaderOptions {
  authService: QoderAuthService
  fetch?: typeof fetch
  ttlMs?: number
  timeoutMs?: number
  region?: QoderRegion
  logger?: QoderLogger
}


interface RawQuota {
  total?: number
  cap?: number
  used?: number
  remaining?: number
  percentage?: number
  unit?: string
  available?: boolean
}

interface RawUsageInfo {
  userQuota?: RawQuota
  orgResourcePackage?: RawQuota
  dedicatedResourcePackages?: unknown
  totalUsagePercentage?: number
  isQuotaExceeded?: boolean
  expiresAt?: number | string
  userType?: string
  upgradeUrl?: string
}

function normalizeQuota(raw?: RawQuota): QoderQuota | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const total = typeof raw.total === 'number' && Number.isFinite(raw.total)
    ? raw.total
    : (typeof raw.cap === 'number' && Number.isFinite(raw.cap)
      ? raw.cap
      : (typeof raw.remaining === 'number' && typeof raw.used === 'number'
        ? raw.used + raw.remaining
        : 0))
  const used = typeof raw.used === 'number' && Number.isFinite(raw.used) ? raw.used : 0
  const remaining = typeof raw.remaining === 'number' && Number.isFinite(raw.remaining)
    ? raw.remaining
    : Math.max(0, total - used)

  let percentage: number
  if (typeof raw.percentage === 'number' && Number.isFinite(raw.percentage)) {
    percentage = raw.percentage <= 1 && total > 1 ? raw.percentage * 100 : raw.percentage
  } else {
    percentage = total > 0 ? (used / total) * 100 : 0
  }

  const unit = typeof raw.unit === 'string' && raw.unit.length > 0 ? raw.unit : 'credits'

  return { total, used, remaining, percentage, unit }
}


/**
 * Normalize an epoch-millis (or parseable date string) expiry to ISO-8601.
 *
 * The provider uses the int64 maximum as a "never expires" sentinel, which is
 * outside the `Date` range: an unusable value resolves to `undefined` instead
 * of throwing, so one bad field cannot abort the whole account read.
 */
function normalizeExpiresAt(rawExpires?: number | string): string | undefined {
  if (rawExpires === undefined || rawExpires === null) return undefined
  const parsed = typeof rawExpires === 'number'
    ? rawExpires
    : (typeof rawExpires === 'string' && rawExpires.length > 0 ? Date.parse(rawExpires) : Number.NaN)
  if (!Number.isFinite(parsed) || parsed <= 0) return undefined
  const date = new Date(parsed)
  if (!Number.isFinite(date.getTime())) return undefined
  return date.toISOString()
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim().length > 0) {
    const num = Number(value)
    if (Number.isFinite(num)) return num
  }
  return undefined
}

/**
 * The provider names a resource package with internal identifiers (campaign
 * ids) that must never reach the UI, so the subscriber-facing copy only ever
 * comes from `displayLabels`.
 */
function findDisplayLabel(raw: unknown, dimension: string): unknown {
  if (!Array.isArray(raw)) return undefined
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue
    const obj = entry as Record<string, unknown>
    if (asString(obj.dimension) === dimension) return obj
  }
  return undefined
}

/**
 * Normalize one `displayLabels` entry into language-tagged copy.
 *
 * The provider's value lives under `valueI18n`/`value_i18n`, keyed by language
 * tag, plus `value` as the untagged fallback. An entry with neither is dropped
 * rather than surfaced as an empty label.
 */
function normalizeLocalizedText(raw: unknown): QoderLocalizedText | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const values: Record<string, string> = {}
  const localized = obj.valueI18n ?? obj.value_i18n
  if (localized && typeof localized === 'object') {
    for (const [locale, text] of Object.entries(localized as Record<string, unknown>)) {
      const resolved = asString(text)
      if (resolved !== undefined) values[locale] = resolved
    }
  }
  const fallback = asString(obj.value)
  if (fallback === undefined && Object.keys(values).length === 0) return undefined
  return { values, fallback: fallback ?? '' }
}

/**
 * Normalize the dedicated (entitlement-scoped) resource packages.
 *
 * Copy is read from `displayLabels` only, never from `name`/`description`,
 * which carry internal campaign identifiers. Entries without a usable size are
 * dropped and a non-array value yields `undefined`, so an unexpected payload
 * never fails the account read that also feeds the model catalog.
 */
function normalizeResourcePackages(raw: unknown): QoderResourcePackage[] | undefined {
  if (!Array.isArray(raw)) return undefined
  const packages: QoderResourcePackage[] = []
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue
    const obj = entry as Record<string, unknown>
    const quota = normalizeQuota(obj as RawQuota)
    // A malformed entry carries no usable size at all: dropping it keeps the
    // rest of the quota panel readable instead of failing the account read.
    if (quota === undefined || (quota.total <= 0 && quota.used <= 0 && quota.remaining <= 0)) continue
    const id = asString(obj.id)
    const title = normalizeLocalizedText(findDisplayLabel(obj.displayLabels ?? obj.display_labels, 'title'))
    const description = normalizeLocalizedText(findDisplayLabel(obj.displayLabels ?? obj.display_labels, 'description'))
    const expiresAt = normalizeExpiresAt(obj.expiresAt as number | string | undefined)
    const available = asBoolean(obj.available)
    const status = asString(obj.status)
    packages.push({
      ...id !== undefined ? { id } : {},
      ...title !== undefined ? { title } : {},
      ...description !== undefined ? { description } : {},
      ...quota,
      ...expiresAt !== undefined ? { expiresAt } : {},
      ...available !== undefined ? { available } : {},
      ...status !== undefined ? { status } : {},
    })
  }
  return packages.length > 0 ? packages : undefined
}

function normalizeOrganization(raw: unknown): QoderSubscriberOrganization | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const orgId = asString(obj.org_id) ?? asString(obj.orgId) ?? asString(obj.id)
  const orgName = asString(obj.org_name) ?? asString(obj.orgName) ?? asString(obj.name)
  if (!orgId || !orgName) return undefined
  return {
    orgId,
    orgName,
    ...asString(obj.role_name) ?? asString(obj.roleName) !== undefined
      ? { roleName: asString(obj.role_name) ?? asString(obj.roleName) }
      : {},
    isSuspended: asBoolean(obj.is_suspended) ?? asBoolean(obj.isSuspended) ?? false,
    canManageSubscriptions: asBoolean(obj.can_manage_subscriptions) ?? asBoolean(obj.canManageSubscriptions) ?? false,
    resourcePackageFeatureEnabled: asBoolean(obj.resource_package_feature_enabled) ?? asBoolean(obj.resourcePackageFeatureEnabled) ?? false,
  }
}

function normalizeFeatureAllowed(raw: unknown): QoderSubscriberFeatureAllowed | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  return {
    quest: asBoolean(obj.quest) ?? false,
    wiki: asBoolean(obj.wiki) ?? false,
    codeReview: asBoolean(obj.code_review) ?? asBoolean(obj.codeReview) ?? false,
  }
}

function normalizePlan(raw: unknown): QoderSubscriberPlan | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const userType = asString(obj.user_type) ?? asString(obj.userType)
  const planTierName = asString(obj.plan_tier_name) ?? asString(obj.planTierName) ?? asString(obj.plan_name) ?? asString(obj.planName)
  if (!userType || !planTierName) return undefined

  const organization = normalizeOrganization(obj.organization)
  const isPersonalVersion = asBoolean(obj.is_personal_version) ?? asBoolean(obj.isPersonalVersion) ?? (organization === undefined)
  const startDate = normalizeExpiresAt(obj.start_date as number | string ?? obj.startDate as number | string)
  const endDate = normalizeExpiresAt(obj.end_date as number | string ?? obj.endDate as number | string)
  const planTier = asString(obj.plan_tier) ?? asString(obj.planTier)
  const isHighestTier = asBoolean(obj.is_highest_tier) ?? asBoolean(obj.isHighestTier)
  const isRenewed = asBoolean(obj.is_renewed) ?? asBoolean(obj.isRenewed)
  const featureAllowed = normalizeFeatureAllowed(obj.feature_allowed ?? obj.featureAllowed)

  return {
    userType,
    planTierName,
    ...planTier !== undefined ? { planTier } : {},
    isPersonalVersion,
    ...isHighestTier !== undefined ? { isHighestTier } : {},
    ...isRenewed !== undefined ? { isRenewed } : {},
    ...startDate !== undefined ? { startDate } : {},
    ...endDate !== undefined ? { endDate } : {},
    ...organization !== undefined ? { organization } : {},
    ...featureAllowed !== undefined ? { featureAllowed } : {},
    raw,
  }
}

function normalizeStatus(raw: unknown): QoderSubscriberStatus | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const featureSwitches = (obj.featureSwitches ?? obj.feature_switches) as Record<string, unknown> | undefined
  const teamSwitches = (obj.teamSwitches ?? obj.team_switches) as Record<string, unknown> | undefined
  const allowByok = asNumber(featureSwitches?.allow_byok ?? featureSwitches?.allowByok) ?? 0
  const teamAllowByok = asNumber(teamSwitches?.allow_byok ?? teamSwitches?.allowByok)
  const isPrivacyPolicyModifiable = asBoolean(obj.isPrivacyPolicyModifiable ?? obj.is_data_policy_modifiable)

  return {
    allowByok,
    ...teamAllowByok !== undefined ? { teamAllowByok } : {},
    ...isPrivacyPolicyModifiable !== undefined ? { isPrivacyPolicyModifiable } : {},
    raw,
  }
}

export class QoderUsageReader {
  private readonly authService: QoderAuthService
  private readonly fetchImpl: typeof fetch
  private readonly ttlMs: number
  private readonly timeoutMs: number
  private readonly region: QoderRegion
  private readonly logger?: QoderLogger
  private readonly cache = new Map<string, { info: QoderAccountInfo; expiresAt: number }>()
  private readonly flights = new SingleFlight<QoderAccountInfo>()

  constructor(options: QoderUsageReaderOptions) {
    this.authService = options.authService
    this.fetchImpl = options.fetch ?? globalThis.fetch
    this.ttlMs = options.ttlMs ?? defaultUsageTtlMs
    this.timeoutMs = options.timeoutMs ?? defaultUsageTimeoutMs
    this.region = options.region ?? 'global'
    this.logger = options.logger
  }

  async readAccount(
    pat: string,
    options?: { force?: boolean; signal?: AbortSignal },
  ): Promise<QoderAccountInfo> {
    if (!pat || typeof pat !== 'string') {
      throw new QoderLlmError(
        'Qoder Personal Access Token is missing or invalid.',
        'MISSING_CREDENTIAL',
      )
    }

    const cacheKey = `${this.region}:${opaqueCredentialKey(pat)}`

    if (!options?.force) {
      const cached = this.cache.get(cacheKey)
      if (cached && cached.expiresAt > Date.now()) {
        return cached.info
      }
    }

    return this.flights.run(
      cacheKey,
      options?.signal,
      sharedSignal => this.loadAccount(pat, sharedSignal, cacheKey),
      () => new QoderLlmError('Qoder account request was aborted.', 'ABORTED'),
    )
  }

  private async loadAccount(
    pat: string,
    signal: AbortSignal,
    cacheKey: string,
  ): Promise<QoderAccountInfo> {
    const creds = await this.authService.getCredentials(pat, signal)
    const profile: QoderSubscriberProfile = {
      id: creds.userID,
      name: creds.name || 'Qoder User',
      email: creds.email || '',
    }

    const [usage, plan, status] = await Promise.all([
      retryMetadataRead(signal, () => this.fetchUsage(creds.authToken, signal)),
      this.safeFetchPlan(creds.authToken, signal),
      this.safeFetchStatus(creds.authToken, creds.machineID, signal),
    ])

    const accountInfo: QoderAccountInfo = {
      profile,
      usage,
      ...plan !== undefined ? { plan } : {},
      ...status !== undefined ? { status } : {},
      updatedAt: new Date().toISOString(),
    }

    this.cache.set(cacheKey, {
      info: accountInfo,
      expiresAt: Date.now() + this.ttlMs,
    })

    return accountInfo
  }

  clear(pat?: string): void {
    if (pat) {
      this.cache.delete(`${this.region}:${opaqueCredentialKey(pat)}`)
    } else {
      this.cache.clear()
    }
  }

  /**
   * Read `GET /api/v2/quota/usage` and normalize it for the host/client seam.
   *
   * The `raw` echo keeps the upstream fields for diagnostics, but never
   * `dedicatedResourcePackages`: those entries carry the campaign identifiers
   * that the normalized list deliberately discards, and this payload crosses
   * the seam into the browser.
   */
  private async fetchUsage(jobToken: string, signal?: AbortSignal): Promise<QoderQuotaUsage> {
    const data = await openApiJsonRequest<RawUsageInfo>(this.fetchImpl, {
      url: getQoderUsageUrl(this.region),
      token: jobToken,
      signal,
      timeoutMs: this.timeoutMs,
      logger: this.logger,
      operation: 'Usage',
      logCategory: 'account.usage',
    })

    const dedicatedResourcePackages = normalizeResourcePackages(data.dedicatedResourcePackages)
    const rawUsage: RawUsageInfo = { ...data }
    delete rawUsage.dedicatedResourcePackages

    return {
      userQuota: normalizeQuota(data.userQuota),
      orgResourcePackage: normalizeQuota(data.orgResourcePackage),
      ...dedicatedResourcePackages !== undefined ? { dedicatedResourcePackages } : {},
      totalUsagePercentage: typeof data.totalUsagePercentage === 'number' ? data.totalUsagePercentage : undefined,
      isQuotaExceeded: typeof data.isQuotaExceeded === 'boolean' ? data.isQuotaExceeded : false,
      expiresAt: normalizeExpiresAt(data.expiresAt),
      raw: rawUsage,
    }
  }

  private async fetchPlan(jobToken: string, signal?: AbortSignal): Promise<QoderSubscriberPlan | undefined> {
    const data = await openApiJsonRequest<unknown>(this.fetchImpl, {
      url: getQoderUserPlanUrl(this.region),
      token: jobToken,
      signal,
      timeoutMs: this.timeoutMs,
      logger: this.logger,
      operation: 'Plan',
      logCategory: 'account.plan',
    })
    return normalizePlan(data)
  }

  private async safeFetchPlan(jobToken: string, signal: AbortSignal): Promise<QoderSubscriberPlan | undefined> {
    try {
      return await this.fetchPlan(jobToken, signal)
    } catch (error) {
      if (signal.aborted) throw error
      this.logger?.warn?.('[Qoder Plan] Failed to load user plan (degraded)', error instanceof Error ? error.message : error)
      return undefined
    }
  }

  private async fetchStatus(
    jobToken: string,
    machineId?: string,
    signal?: AbortSignal,
  ): Promise<QoderSubscriberStatus | undefined> {
    const data = await openApiJsonRequest<unknown>(this.fetchImpl, {
      url: getQoderUserStatusUrl(this.region),
      token: jobToken,
      machineId,
      signal,
      timeoutMs: this.timeoutMs,
      logger: this.logger,
      operation: 'Status',
      logCategory: 'account.status',
    })
    return normalizeStatus(data)
  }

  private async safeFetchStatus(
    jobToken: string,
    machineId?: string,
    signal?: AbortSignal,
  ): Promise<QoderSubscriberStatus | undefined> {
    try {
      return await this.fetchStatus(jobToken, machineId, signal)
    } catch (error) {
      if (signal?.aborted) throw error
      this.logger?.warn?.('[Qoder Status] Failed to load user status (degraded)', error instanceof Error ? error.message : error)
      return undefined
    }
  }
}
