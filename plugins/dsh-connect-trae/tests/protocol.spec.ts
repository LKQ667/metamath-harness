import { describe, expect, it } from 'vitest'
import { buildTraeAgentTaskBody, buildTraeCnHeaders, normalizeTraeVersionCode, TRAE_CN_AGENT_TASK_PATH, TRAE_CN_TITLE_PATH, TRAE_VERSION_CODE_FALLBACK, traeEndpoint } from '../src/protocol.ts'
import type { TraeCredential } from '../src/auth.ts'
import type { TraeIdentity } from '../src/identity.ts'

const credential: TraeCredential = {
  accessToken: 'secret-access', refreshToken: 'secret-refresh', userId: 'uid', host: 'https://trae-api-cn.mchost.guru',
  expiresAtMs: Date.now() + 60_000, edition: 'cn', source: 'desktop',
}
const identity: TraeIdentity = {
  edition: 'cn', machineId: 'machine-stable', deviceId: 'device-stable', buildVersion: '20260716', appVersion: '3.3.79', platform: 'darwin',
}

describe('Trae CN protocol draft', () => {
  it('keeps title and agent-task endpoints semantically separate', () => {
    expect(TRAE_CN_TITLE_PATH).toBe('/api/agent/v3/llm_utils_chat')
    expect(TRAE_CN_AGENT_TASK_PATH).toBe('/api/agent/v3/create_agent_task')
    expect(TRAE_CN_TITLE_PATH).not.toBe(TRAE_CN_AGENT_TASK_PATH)
    expect(traeEndpoint('https://host/', TRAE_CN_AGENT_TASK_PATH)).toBe('https://host/api/agent/v3/create_agent_task')
  })

  it('constructs a deterministic offline body when IDs are provided', () => {
    const body = buildTraeAgentTaskBody([{ role: 'user', content: 'hello' }], 'glm-5.2', { requestId: 'req', sessionId: 'session', maxTokens: 100 })
    expect(body).toEqual({
      messages: [{ role: 'user', content: [{ type: 'text', text: 'hello' }] }],
      model: 'glm-5.2', function: 'inline_chat', stream: true, request_id: 'req', session_id: 'session', max_tokens: 100,
    })
  })

  it('uses persisted identity and matched request IDs in CN headers', () => {
    const headers = buildTraeCnHeaders(credential, identity, { requestId: 'request-one' })
    expect(headers).toMatchObject({
      Authorization: 'Cloud-IDE-JWT secret-access', 'X-Cloudide-Token': 'secret-access', 'x-uid': 'uid',
      'x-machine-id': 'machine-stable', 'x-device-id': 'device-stable', 'x-device-type': 'mac',
      'x-request-id': 'request-one', 'x-trae-request-id': 'request-one', Accept: 'text/event-stream',
    })
  })

  it('uses endpoint-specific auth profiles for model detail and Raw Chat', () => {
    const detail = buildTraeCnHeaders(credential, identity, { requestId: 'detail', profile: 'model-detail' })
    const raw = buildTraeCnHeaders(credential, identity, { requestId: 'raw', profile: 'raw-chat' })
    for (const headers of [detail, raw]) {
      expect(headers).toMatchObject({
        Authorization: 'Cloud-IDE-JWT secret-access',
        'X-Ide-Token': 'secret-access',
        'x-plugin-channel': 'icube-ai',
      })
      expect(headers).not.toHaveProperty('X-Cloudide-Token')
      expect(headers).not.toHaveProperty('x-uid')
      expect(headers).not.toHaveProperty('x-request-id')
      expect(headers).not.toHaveProperty('x-trae-request-id')
    }
    expect(detail.Accept).toBe('application/json')
    expect(raw.Accept).toBe('text/event-stream')
  })

  it('matches the exact native curl diagnostic header set', () => {
    const headers = buildTraeCnHeaders(credential, identity, { requestId: 'native', profile: 'native-curl' })
    expect(headers).toMatchObject({ 'X-Ide-Token': 'secret-access', 'x-app-id': expect.any(String), 'Content-Type': 'application/json' })
    expect(headers).not.toHaveProperty('Authorization')
    expect(headers).not.toHaveProperty('x-plugin-channel')
    expect(headers).not.toHaveProperty('User-Agent')
    expect(headers).not.toHaveProperty('Accept')
  })

  it('sends a bindable numeric version code even when Trae persists a dotted build', () => {
    // TRAE SOLO CN 0.1.56 stores iCubeLastVersion as "2.3.76922"; the upstream
    // binds the version code as a number and rejects that with 4001.
    const dotted: TraeIdentity = { ...identity, buildVersion: '2.3.76922' }
    const headers = buildTraeCnHeaders(credential, dotted, { requestId: 'dotted' })
    expect(headers['x-app-version-code']).toBe(TRAE_VERSION_CODE_FALLBACK)
    expect(headers['x-ide-version-code']).toBe(TRAE_VERSION_CODE_FALLBACK)
    // Everything else stays truthful: no device impersonation.
    expect(headers['x-machine-id']).toBe('machine-stable')
    expect(headers['x-device-id']).toBe('device-stable')
    expect(headers['x-ide-version']).toBe('3.3.79')
  })

  it('keeps an already numeric build version as-is', () => {
    const numeric: TraeIdentity = { ...identity, buildVersion: '20260716' }
    expect(buildTraeCnHeaders(credential, numeric)['x-app-version-code']).toBe('20260716')
    expect(normalizeTraeVersionCode('20260716')).toBe('20260716')
    expect(normalizeTraeVersionCode(undefined)).toBe(TRAE_VERSION_CODE_FALLBACK)
    expect(normalizeTraeVersionCode('')).toBe(TRAE_VERSION_CODE_FALLBACK)
  })

  it('refuses to reuse the CN request contract for SG', () => {
    expect(() => buildTraeCnHeaders({ ...credential, edition: 'sg' }, { ...identity, edition: 'sg' })).toThrow(/not verified/)
  })
})
