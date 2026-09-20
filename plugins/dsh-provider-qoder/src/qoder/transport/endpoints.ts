/** Qoder transport endpoints for Global and China service regions. */

import type { QoderRegion } from '../region.ts'

export type { QoderRegion } from '../region.ts'

export interface QoderRegionEndpoints {
  baseUrl: string
  openApiUrl: string
  /** Center service that owns durable image objects for multimodal input. */
  centerUrl: string
}

export const qoderRegionEndpoints: Record<QoderRegion, QoderRegionEndpoints> = {
  global: {
    baseUrl: 'https://api3.qoder.sh/',
    openApiUrl: 'https://openapi.qoder.sh',
    centerUrl: 'https://center.qoder.sh',
  },
  china: {
    baseUrl: 'https://gateway.qoder.com.cn/',
    openApiUrl: 'https://openapi.qoder.com.cn',
    centerUrl: 'https://gateway.qoder.com.cn',
  },
}

/** Signed path of the center image upload route; it never carries an `/algo` prefix. */
export const qoderImageUploadPath = '/api/v2/image/upload'

export const qoderGlobalBaseUrl = qoderRegionEndpoints.global.baseUrl
export const qoderGlobalOpenApiUrl = qoderRegionEndpoints.global.openApiUrl

export function resolveQoderEndpoints(region: QoderRegion = 'global'): QoderRegionEndpoints {
  return qoderRegionEndpoints[region] ?? qoderRegionEndpoints.global
}

export function getQoderChatUrl(region: QoderRegion = 'global'): string {
  const { baseUrl } = resolveQoderEndpoints(region)
  return `${baseUrl}algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1`
}

export function getQoderModelListUrl(region: QoderRegion = 'global'): string {
  const { baseUrl } = resolveQoderEndpoints(region)
  return `${baseUrl}algo/api/v2/model/list?Encode=1`
}

export function getQoderImageUploadUrl(region: QoderRegion = 'global', requestId?: string): string {
  const { centerUrl } = resolveQoderEndpoints(region)
  // qodercli's WASM prepareRequest adds /algo to the HTTP URL, but not the signature path.
  const base = `${centerUrl.replace(/\/+$/u, '')}/algo${qoderImageUploadPath}`
  return requestId === undefined ? base : `${base}?request_id=${encodeURIComponent(requestId)}`
}

export function getQoderExchangeUrl(region: QoderRegion = 'global'): string {
  const { openApiUrl } = resolveQoderEndpoints(region)
  return `${openApiUrl}/api/v1/jobToken/exchange`
}

export function getQoderUserInfoUrl(region: QoderRegion = 'global'): string {
  const { openApiUrl } = resolveQoderEndpoints(region)
  return `${openApiUrl}/api/v1/userinfo`
}

export function getQoderUsageUrl(region: QoderRegion = 'global'): string {
  const { openApiUrl } = resolveQoderEndpoints(region)
  return `${openApiUrl}/api/v2/quota/usage`
}

export function getQoderUserPlanUrl(region: QoderRegion = 'global'): string {
  const { openApiUrl } = resolveQoderEndpoints(region)
  return `${openApiUrl}/api/v2/user/plan`
}

export function getQoderUserStatusUrl(region: QoderRegion = 'global'): string {
  const { openApiUrl } = resolveQoderEndpoints(region)
  return `${openApiUrl}/api/v3/user/status`
}

/** Path of the center web search route. */
export const qoderWebSearchPath = '/api/v1/webSearch/oneSearch'

export function getQoderWebSearchUrl(region: QoderRegion = 'global'): string {
  const { centerUrl } = resolveQoderEndpoints(region)
  return `${centerUrl.replace(/\/+$/u, '')}/algo${qoderWebSearchPath}?Encode=1`
}

