import { randomUUID } from 'node:crypto'
import type { TraeCredential } from './auth.ts'
import type { TraeIdentity } from './identity.ts'
import { identityHeaders } from './identity.ts'

export const TRAE_CN_AGENT_TASK_PATH = '/api/agent/v3/create_agent_task'
export const TRAE_CN_TITLE_PATH = '/api/agent/v3/llm_utils_chat'

export interface OpenAITextMessage {
  role: 'assistant' | 'system' | 'user'
  content: string
}

export interface TraeAgentTaskBody {
  messages: { role: OpenAITextMessage['role']; content: { type: 'text'; text: string }[] }[]
  model: string
  function: string
  stream: true
  request_id: string
  session_id: string
  max_tokens?: number
}

/**
 * Evidence-bounded body draft. It is intentionally pure and offline; the
 * network client remains disabled until a controlled request validates it.
 */
export function buildTraeAgentTaskBody(
  messages: readonly OpenAITextMessage[],
  model: string,
  options: { maxTokens?: number; requestId?: string; sessionId?: string } = {},
): TraeAgentTaskBody {
  if (messages.length === 0) throw new Error('Trae agent task requires at least one message')
  const requestId = options.requestId ?? randomUUID()
  const sessionId = options.sessionId ?? requestId
  return {
    messages: messages.map(message => ({ role: message.role, content: [{ type: 'text', text: message.content }] })),
    model,
    function: 'inline_chat',
    stream: true,
    request_id: requestId,
    session_id: sessionId,
    ...options.maxTokens === undefined ? {} : { max_tokens: options.maxTokens },
  }
}

export type TraeHeaderProfile = 'agent-task' | 'model-detail' | 'raw-chat' | 'native-curl'

/**
 * Numeric version code sent when the persisted build version is not a plain
 * integer. The upstream binds `x-app-version-code` / `x-ide-version-code` as a
 * number: Trae stores `iCubeLastVersion` as a dotted build string (observed
 * `2.3.76922` on TRAE SOLO CN 0.1.56), which the server rejects with
 * `4001 ... expr_path=app_version_code, cause=parameter type does not match
 * binding data`. Verified 2026-08-29: with a numeric code the same request
 * returns HTTP 200 + `text/event-stream` on
 * `/api/agent/v3/llm_utils_chat` (`solo_work_lite`).
 *
 * Only the *format* of this field is normalised. Machine, device and app
 * version stay exactly as persisted — nothing here impersonates a device.
 */
export const TRAE_VERSION_CODE_FALLBACK = '20260716'

/** Keep a purely numeric build version; fall back when it cannot bind. */
export function normalizeTraeVersionCode(buildVersion: string | undefined): string {
  if (buildVersion === undefined || buildVersion.trim() === '') return TRAE_VERSION_CODE_FALLBACK
  const trimmed = buildVersion.trim()
  return /^\d+$/.test(trimmed) ? trimmed : TRAE_VERSION_CODE_FALLBACK
}

export function buildTraeCnHeaders(
  credential: TraeCredential,
  identity: TraeIdentity,
  options: { appId?: string; requestId?: string; profile?: TraeHeaderProfile } = {},
): Record<string, string> {
  if (credential.edition !== 'cn' && credential.edition !== 'solo') {
    throw new Error(`Trae ${credential.edition} request contract is not verified`)
  }
  const requestId = options.requestId ?? randomUUID()
  const traceId = requestId.replaceAll('-', '').slice(0, 32)
  const profile = options.profile ?? 'agent-task'
  const common = {
    'Authorization': `Cloud-IDE-JWT ${credential.accessToken}`,
    'X-Ide-Token': credential.accessToken,
    'x-plugin-channel': 'icube-ai',
    'User-Agent': `Trae/${identity.appVersion ?? identity.buildVersion ?? 'unknown'}`,
    'x-app-id': options.appId ?? '6eefa01c-1036-4c7e-9ca5-d891f63bfcd8',
    ...identityHeaders(identity),
    // The upstream binds these as numbers; a dotted build string is rejected.
    'x-app-version-code': normalizeTraeVersionCode(identity.buildVersion),
    'x-ide-version-code': normalizeTraeVersionCode(identity.buildVersion),
    'x-custom-trace-id': traceId,
    'x-flow-traceparent': `04-${traceId}-${traceId.slice(0, 16)}-01`,
    'request-traffic-type': 'prod',
    'Content-Type': 'application/json',
  }
  if (profile === 'native-curl') {
    // Exact set printed by Trae 3.3.83's own get_skill_detail curl diagnostic.
    // No Authorization, plugin channel, User-Agent or speculative bridge headers.
    return {
      'Content-Type': 'application/json',
      'request-traffic-type': 'prod',
      'x-app-id': options.appId ?? '6eefa01c-1036-4c7e-9ca5-d891f63bfcd8',
      ...identityHeaders(identity),
      'x-custom-trace-id': traceId,
      'x-flow-traceparent': `04-${traceId}-${traceId.slice(0, 16)}-01`,
      'X-Ide-Token': credential.accessToken,
    }
  }
  if (profile === 'model-detail') return { ...common, 'Accept': 'application/json' }
  if (profile === 'raw-chat') return { ...common, 'Accept': 'text/event-stream' }
  return {
    ...common,
    'X-Cloudide-Token': credential.accessToken,
    'x-uid': credential.userId,
    'x-request-id': requestId,
    'x-trae-request-id': requestId,
    'Accept': 'text/event-stream',
  }
}

export function traeEndpoint(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}
