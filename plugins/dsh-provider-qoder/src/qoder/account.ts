/** Browser-safe Qoder subscriber account and quota types. */

export interface QoderSubscriberProfile {
  id: string
  name: string
  email: string
}

export interface QoderQuota {
  total: number
  used: number
  remaining: number
  percentage: number
  unit: string
}

/**
 * Provider copy carried verbatim across the host/client seam.
 *
 * The host has no browser language, so it never picks one: the language map
 * travels intact and the client resolves it against the active UI locale.
 */
export interface QoderLocalizedText {
  /** Language tag (e.g. 'zh-CN', 'en-US') to copy. */
  values: Readonly<Record<string, string>>
  /** Provider copy that carries no language tag; empty when absent. */
  fallback: string
}

/** One dedicated (entitlement-scoped) resource package carved out of the plan. */
export interface QoderResourcePackage {
  id?: string
  title?: QoderLocalizedText
  description?: QoderLocalizedText
  total: number
  used: number
  remaining: number
  percentage: number
  unit: string
  /** Package expiry, distinct from the usage-level subscription expiry. */
  expiresAt?: string
  available?: boolean
  status?: string
}

export interface QoderQuotaUsage {
  userQuota?: QoderQuota
  orgResourcePackage?: QoderQuota
  dedicatedResourcePackages?: QoderResourcePackage[]
  totalUsagePercentage?: number
  isQuotaExceeded?: boolean
  expiresAt?: string
  raw?: unknown
}

export interface QoderSubscriberOrganization {
  orgId: string
  orgName: string
  roleName?: string
  isSuspended?: boolean
  canManageSubscriptions?: boolean
  resourcePackageFeatureEnabled?: boolean
}

export interface QoderSubscriberFeatureAllowed {
  quest?: boolean
  wiki?: boolean
  codeReview?: boolean
}

export interface QoderSubscriberPlan {
  userType: string
  planTierName: string
  planTier?: string
  isPersonalVersion: boolean
  isHighestTier?: boolean
  isRenewed?: boolean
  startDate?: string
  endDate?: string
  organization?: QoderSubscriberOrganization
  featureAllowed?: QoderSubscriberFeatureAllowed
  raw?: unknown
}

export interface QoderSubscriberStatus {
  allowByok: number
  teamAllowByok?: number
  isPrivacyPolicyModifiable?: boolean
  raw?: unknown
}

export interface QoderAccountInfo {
  profile: QoderSubscriberProfile
  usage?: QoderQuotaUsage
  plan?: QoderSubscriberPlan
  status?: QoderSubscriberStatus
  updatedAt: string
}
