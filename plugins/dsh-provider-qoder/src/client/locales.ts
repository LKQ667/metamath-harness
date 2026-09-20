import type { QoderLocalizedText } from '../qoder/account.ts'

export const zh = {
  nav: 'Qoder',
  title: 'Qoder 凭据',
  configured: '已配置',
  missing: '未配置',
  loading: '正在读取凭据状态…',
  loadFailed: '无法读取凭据状态。',
  retry: '重试',
  edit: '编辑',
  cancel: '取消',
  regionLabel: '服务区域',
  regionGlobal: '国际版 (Global)',
  regionChina: '中国区 (CN)',
  regionHint: '请确保 PAT 与所选服务区域匹配。',
  tokenLabel: 'API 密钥',
  tokenPlaceholder: '输入新的 Personal Access Token',
  configuredHint: '已配置——输入新值可替换',
  readOnly: '当前凭据存储不可写。',
  save: '保存',
  saving: '正在保存…',
  saved: 'Qoder 设置已保存。',
  saveFailed: 'Qoder 设置保存失败，请重试。',
  remove: '删除',
  removing: '正在删除…',
  removeFailed: '凭据删除失败，请重试。',
  confirmRemove: '删除已保存的 Qoder 凭据？删除后，新的模型请求将无法运行。',
  customized: '自定义设置',
  modelsTitle: '模型目录',
  modelsLoading: '正在读取模型设置…',
  modelsUnavailable: '当前无法读取或保存模型设置。',
  modelsEnabled: '已启用 {count} 个模型',
  modelsFetch: '获取可用模型',
  modelsFetching: '正在获取…',
  modelsFetchFailed: '无法获取可用模型。',
  modelsRequired: '至少需要保留一个模型。',
  modelUnavailable: '不可用',
  modelRate: '{value}x',
  modelRateUnknown: '倍率未知',
  accountTitle: 'Qoder',
  accountLoading: '正在读取账号与额度…',
  accountFailed: '无法读取账号信息与额度。',
  accountCredentialHint: '请先在“模型”设置中配置 Qoder Personal Access Token。',
  refresh: '刷新',
  refreshing: '正在刷新…',
  userQuotaTitle: '个人额度',
  orgResourceTitle: '组织资源包',
  dedicatedResourceTitle: '专属资源包',
  dedicatedResourceExpiresAt: '有效期至：{value}',
  quotaRemaining: '剩余 {value}%',
  quotaUsed: '已用 {used} / {total} {unit}',
  resetsAt: '重置时间：{value}',
  noQuota: '暂无可用额度信息',
  quotaExceeded: '当前订阅额度已用尽。',
  plan: '套餐计划',
  planExpiresAt: '有效期至：{value}',
  organization: '组织：{name}',
  accountSuspended: '当前账号或组织已被暂停/冻结。',
  searchModeLabel: '联网搜索模式',
  searchModeAuto: '智能路由 (自动)',
  searchModeAlways: '始终使用 Qoder',
  searchModeDisabled: '禁用',
  searchModeHint: '智能路由模式下，使用 Qoder 模型时走 Qoder 搜索，使用其他模型时自动回退给备用搜索。',
}

export const en: typeof zh = {
  nav: 'Qoder',
  title: 'Qoder credential',
  configured: 'Configured',
  missing: 'Not configured',
  loading: 'Reading credential status…',
  loadFailed: 'Could not read credential status.',
  retry: 'Retry',
  edit: 'Edit',
  cancel: 'Cancel',
  regionLabel: 'Service Region',
  regionGlobal: 'Global',
  regionChina: 'China (CN)',
  regionHint: 'Ensure your PAT matches the selected service region.',
  tokenLabel: 'API Key',
  tokenPlaceholder: 'Enter a new Personal Access Token',
  configuredHint: 'Configured — enter a new value to replace',
  readOnly: 'The current credential store is read-only.',
  save: 'Save',
  saving: 'Saving…',
  saved: 'Qoder settings saved.',
  saveFailed: 'Could not save the Qoder settings. Try again.',
  remove: 'Remove',
  removing: 'Removing…',
  removeFailed: 'Could not remove the credential. Try again.',
  confirmRemove: 'Remove the stored Qoder credential? New model requests will stop working.',
  customized: 'Custom settings',
  modelsTitle: 'Model catalog',
  modelsLoading: 'Reading model settings…',
  modelsUnavailable: 'Model settings cannot currently be read or saved.',
  modelsEnabled: '{count} models enabled',
  modelsFetch: 'Fetch available models',
  modelsFetching: 'Fetching…',
  modelsFetchFailed: 'Could not fetch available models.',
  modelsRequired: 'Keep at least one model.',
  modelUnavailable: 'Unavailable',
  modelRate: '{value}x',
  modelRateUnknown: 'Rate unknown',
  accountTitle: 'Qoder',
  accountLoading: 'Reading account and quota…',
  accountFailed: 'Could not read account details or quota.',
  accountCredentialHint: 'Configure the Qoder Personal Access Token in Models settings first.',
  refresh: 'Refresh',
  refreshing: 'Refreshing…',
  userQuotaTitle: 'Personal Quota',
  orgResourceTitle: 'Org Resource Package',
  dedicatedResourceTitle: 'Dedicated Resource Package',
  dedicatedResourceExpiresAt: 'Expires at: {value}',
  quotaRemaining: '{value}% remaining',
  quotaUsed: 'Used {used} / {total} {unit}',
  resetsAt: 'Resets: {value}',
  noQuota: 'No quota metrics available',
  quotaExceeded: 'The current subscription quota is exhausted.',
  plan: 'Plan',
  planExpiresAt: 'Expires at: {value}',
  organization: 'Org: {name}',
  accountSuspended: 'Account or organization is currently suspended.',
  searchModeLabel: 'Web Search Mode',
  searchModeAuto: 'Smart Routing (Auto)',
  searchModeAlways: 'Always use Qoder',
  searchModeDisabled: 'Disabled',
  searchModeHint: 'In auto mode, searches route to Qoder when using Qoder models, and fall back to ambient providers otherwise.',
}


export type QoderCredentialCopy = keyof typeof zh

/**
 * Compare one provider language tag against the requested locale.
 *
 * `prefix` additionally accepts a shared primary subtag, which is what lets the
 * built-in `zh`/`en` ids reach the provider's `zh-CN`/`en-US` keys.
 */
function localeMatches(tag: string, requested: string, prefix: boolean): boolean {
  const normalized = tag.trim().toLowerCase()
  if (normalized === requested) return true
  if (!prefix) return false
  const primary = requested.split('-')[0]
  return primary.length > 0 && normalized.split('-')[0] === primary
}

/**
 * Return the first provider translation whose language tag matches the request.
 *
 * `prefix` decides whether a shared primary subtag counts as a match; blank
 * translations are skipped so they cannot shadow a later usable one.
 */
function pickLocalizedValue(
  values: Readonly<Record<string, string>>,
  requested: string,
  prefix: boolean,
): string | undefined {
  for (const [tag, value] of Object.entries(values)) {
    if (!localeMatches(tag, requested, prefix)) continue
    const text = typeof value === 'string' ? value.trim() : ''
    if (text.length > 0) return text
  }
  return undefined
}

/**
 * Resolve provider copy for the active UI locale.
 *
 * Order: exact language tag, then a shared primary subtag, then the provider's
 * language-neutral fallback, then any translation at all. The client owns this
 * choice because only it knows the locale the user is reading.
 */
export function resolveLocalizedText(
  text: QoderLocalizedText | undefined,
  locale: string,
): string | undefined {
  if (!text) return undefined
  const values = text.values ?? {}
  const requested = typeof locale === 'string' ? locale.trim().toLowerCase() : ''
  if (requested.length > 0) {
    const exact = pickLocalizedValue(values, requested, false)
    if (exact !== undefined) return exact
    const related = pickLocalizedValue(values, requested, true)
    if (related !== undefined) return related
  }
  const fallback = typeof text.fallback === 'string' ? text.fallback.trim() : ''
  if (fallback.length > 0) return fallback
  for (const value of Object.values(values)) {
    const candidate = typeof value === 'string' ? value.trim() : ''
    if (candidate.length > 0) return candidate
  }
  return undefined
}
