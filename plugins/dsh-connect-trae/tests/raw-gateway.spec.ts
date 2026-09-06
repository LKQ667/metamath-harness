import { describe, expect, it, vi } from 'vitest'
import { createTraeRawGateway } from '../src/raw-gateway.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

const success = (text: string) => ({ ok: true as const, response: new Response(text) })

describe('Trae Raw gateway assembly', () => {
  it('is disabled by default and uses SOLO without probing Raw', async () => {
    const raw = { chatStream: vi.fn(async () => success('raw')) } satisfies TraeUpstreamClient
    const solo = { chatStream: vi.fn(async () => success('solo')) } satisfies TraeUpstreamClient
    const gateway = createTraeRawGateway({
      raw, solo, endpoint: 'https://host/raw', edition: 'cn', identity: { appVersion: '1' },
      runtime: { configName: 'm', modelName: 'm' },
    })
    const result = await gateway.upstream.chatStream('{}')
    expect(result.ok && await result.response.text()).toBe('solo')
    expect(raw.chatStream).not.toHaveBeenCalled()
    expect(gateway.diagnostic()).toEqual({ state: 'disabled' })
    await gateway.probe()
    expect(raw.chatStream).not.toHaveBeenCalled()
  })

  it('uses Raw only after an enabled successful probe', async () => {
    const raw = { chatStream: vi.fn(async () => success('raw')) } satisfies TraeUpstreamClient
    const solo = { chatStream: vi.fn(async () => success('solo')) } satisfies TraeUpstreamClient
    const gateway = createTraeRawGateway({
      raw, solo, endpoint: 'https://host/raw', edition: 'cn', identity: { appVersion: '1' },
      runtime: { configName: 'm', modelName: 'm' }, enabled: true,
    })
    await expect(gateway.probe()).resolves.toMatchObject({ available: true })
    expect(gateway.diagnostic()).toMatchObject({ state: 'available' })
    const result = await gateway.upstream.chatStream('{}')
    expect(result.ok && await result.response.text()).toBe('raw')
    expect(raw.chatStream).toHaveBeenCalledTimes(2)
  })
})
