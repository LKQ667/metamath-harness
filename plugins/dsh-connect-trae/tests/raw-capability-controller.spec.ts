import { describe, expect, it, vi } from 'vitest'
import { TraeRawCapabilityController } from '../src/raw-capability-controller.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

describe('TraeRawCapabilityController', () => {
  it('does not touch the network until explicitly enabled', async () => {
    const client = { chatStream: vi.fn() } as unknown as TraeUpstreamClient
    const controller = new TraeRawCapabilityController({ client })
    await expect(controller.probe('a')).resolves.toEqual({ available: false, reason: 'protocol', status: 0 })
    expect(client.chatStream).not.toHaveBeenCalled()
  })

  it('single-flights and caches an enabled probe', async () => {
    const client = { chatStream: vi.fn(async () => ({ ok: false as const, status: 400, kind: 'client' as const, message: '' })) } satisfies TraeUpstreamClient
    const controller = new TraeRawCapabilityController({ client, enabled: true })
    const [a, b] = await Promise.all([controller.probe('fp'), controller.probe('fp')])
    expect(a).toEqual({ available: false, reason: 'protocol', status: 400 })
    expect(b).toEqual(a)
    expect(client.chatStream).toHaveBeenCalledTimes(1)
    await controller.probe('fp')
    expect(client.chatStream).toHaveBeenCalledTimes(1)
  })

  it('invalidates when enablement changes', async () => {
    const client = { chatStream: vi.fn(async () => ({ ok: false as const, status: 400, kind: 'client' as const, message: '' })) } satisfies TraeUpstreamClient
    const controller = new TraeRawCapabilityController({ client, enabled: true })
    await controller.probe('fp')
    controller.setEnabled(false)
    controller.setEnabled(true)
    await controller.probe('fp')
    expect(client.chatStream).toHaveBeenCalledTimes(2)
  })
})
