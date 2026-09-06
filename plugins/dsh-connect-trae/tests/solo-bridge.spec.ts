import { describe, expect, it } from 'vitest'
import { bridgeTraeSoloStream, TraeSoloBridge } from '../src/solo-bridge.ts'
import type { TraeUpstreamClient } from '../src/upstream.ts'

function traeStream(events: string[]): Response {
  return new Response(events.join(''), { headers: { 'content-type': 'text/event-stream' } })
}

describe('TraeSoloBridge', () => {
  it('converts Trae function_call deltas into OpenAI tool_calls', async () => {
    const upstream: TraeUpstreamClient = {
      async chatStream() {
        return { ok: true, response: traeStream([
          'event: output\ndata: {"response":"","tool_calls":[{"index":0,"id":"call-1","type":"function","function_call":{"name":"read","arguments":"{\\"file_path\\":\\"README.md\\"}"}}]}\n\n',
          'event: done\ndata: {"finish_reason":"stop"}\n\n',
        ]) }
      },
    }
    const bridge = new TraeSoloBridge(upstream)
    const result = await bridge.chatStream(JSON.stringify({ model: 'glm-5.2', messages: [{ role: 'user', content: 'read' }] }))
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const text = await result.response.text()
    expect(text).toContain('"tool_calls":[{"index":0,"id":"call-1","type":"function","function":{"name":"read","arguments":"{\\"file_path\\":\\"README.md\\"}"}}]')
    expect(text).toContain('"finish_reason":"tool_calls"')
    expect(text).toContain('data: [DONE]')
  })

  it('synthesizes one finish_reason before [DONE] when Trae ends at clean EOF', async () => {
    const response = bridgeTraeSoloStream(traeStream([
      'event: output\ndata: {"response":"hello"}\n\n',
    ]), 'm')
    const text = await response.text()
    const finishChunks = text.split('\n\n').filter(line => line.includes('"finish_reason":"stop"'))
    expect(finishChunks).toHaveLength(1)
    expect(text.indexOf('"finish_reason":"stop"')).toBeLessThan(text.indexOf('data: [DONE]'))
  })

  it('emits only one finish_reason when Trae sends done and trailing [DONE]', async () => {
    const response = bridgeTraeSoloStream(traeStream([
      'event: output\ndata: {"response":"hello"}\n\n',
      'event: done\ndata: {"finish_reason":"stop"}\n\n',
      'data: [DONE]\n\n',
    ]), 'm')
    const text = await response.text()
    expect(text.match(/"finish_reason":"stop"/g)).toHaveLength(1)
    expect(text).toContain('data: [DONE]')
  })

  it('propagates an upstream error followed by done without emitting a finish chunk', async () => {
    const response = bridgeTraeSoloStream(traeStream([
      'event: error\ndata: {"code":4008,"message":"quota exceeded"}\n\n',
      'event: done\ndata: {"finish_reason":"stop"}\n\n',
    ]), 'm')
    const reader = response.body!.getReader()
    await expect(reader.read()).rejects.toThrow('quota exceeded')
  })

  it('synthesizes tool_calls finish_reason when a tool stream ends at EOF', async () => {
    const response = bridgeTraeSoloStream(traeStream([
      'event: output\ndata: {"response":"","tool_calls":[{"index":0,"id":"call-eof","type":"function","function_call":{"name":"read","arguments":"{}"}}]}\n\n',
    ]), 'm')
    const text = await response.text()
    expect(text).toContain('"finish_reason":"tool_calls"')
    expect(text.indexOf('"finish_reason":"tool_calls"')).toBeLessThan(text.indexOf('data: [DONE]'))
  })

  it('preserves split tool-call argument deltas', async () => {
    const event = (name: string, data: unknown): string => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`
    const response = bridgeTraeSoloStream(traeStream([
      event('output', { tool_calls: [{ index: 0, id: 'call-2', type: 'function', function_call: { name: 'edit', arguments: '{"file"' } }] }),
      event('output', { tool_calls: [{ index: 0, function_call: { name: '', arguments: ':"a"}' } }] }),
      event('done', { finish_reason: 'stop' }),
    ]), 'm')
    const text = await response.text()
    expect(text).toContain('"name":"edit"')
    expect(text).toContain('"arguments":"{\\"file\\""')
    expect(text).toContain('"arguments":":\\"a\\"}"')
  })

  it('strips a stale reasoning effort when the selected model does not advertise it', async () => {
    let forwarded = ''
    const upstream: TraeUpstreamClient = {
      async chatStream(bodyJson) {
        forwarded = bodyJson
        return { ok: true, response: traeStream(['event: done\ndata: {"finish_reason":"stop"}\n\n']) }
      },
    }
    const catalog = {
      current: () => [{ id: 'Doubao-Seed-Code', name: 'Doubao-Seed-Code', input: ['text', 'image'] as ('text' | 'image')[] }],
    }
    const result = await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'Doubao-Seed-Code', reasoning_effort: 'high', messages: [{ role: 'user', content: 'hi' }],
    }))
    expect(result.ok).toBe(true)
    expect(JSON.parse(forwarded)).not.toHaveProperty('reasoning_effort')
  })

  it('maps canonical DSH reasoning effort to the selected model wire value', async () => {
    let forwarded = ''
    const upstream: TraeUpstreamClient = {
      async chatStream(bodyJson) {
        forwarded = bodyJson
        return { ok: true, response: traeStream(['event: done\ndata: {"finish_reason":"stop"}\n\n']) }
      },
    }
    const catalog = {
      current: () => [{ id: 'qwen', name: 'Qwen', reasoningEfforts: { low: 'light', high: 'high', xhigh: 'extra_high' } }],
    }
    await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'qwen', reasoning_effort: 'low', messages: [{ role: 'user', content: 'hi' }],
    }))
    expect(JSON.parse(forwarded)).toHaveProperty('reasoning_effort', 'light')
    await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'qwen', reasoning_effort: 'xhigh', messages: [{ role: 'user', content: 'hi' }],
    }))
    expect(JSON.parse(forwarded)).toHaveProperty('reasoning_effort', 'extra_high')
  })

  it('resolves the display model id to its wire config_name for the upstream', async () => {
    let forwarded = ''
    const upstream: TraeUpstreamClient = {
      async chatStream(bodyJson) {
        forwarded = bodyJson
        return { ok: true, response: traeStream(['event: done\ndata: {"finish_reason":"stop"}\n\n']) }
      },
    }
    const catalog = {
      current: () => [{ id: 'Doubao-Seed-Code', name: 'Seed-Code', input: ['text'] as ('text' | 'image')[], wireConfigName: 'Doubao_1_6' }],
    }
    const result = await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'Doubao-Seed-Code', messages: [{ role: 'user', content: '1+1' }],
    }))
    expect(result.ok).toBe(true)
    const forwardedBody = JSON.parse(forwarded) as Record<string, unknown>
    expect(forwardedBody['model']).toBe('Doubao_1_6')
    // The SSE chunk label stays the display id the caller requested.
    const response = result.ok ? result.response : undefined
    expect(await response?.text()).toContain('"model":"Doubao-Seed-Code"')
  })

  it('falls back to the startup wire resolver when the catalog lacks wireConfigName', async () => {
    let forwarded = ''
    const upstream: TraeUpstreamClient = {
      async chatStream(bodyJson) {
        forwarded = bodyJson
        return { ok: true, response: traeStream(['event: done\ndata: {"finish_reason":"stop"}\n\n']) }
      },
    }
    // A persisted catalog that was saved before the schema kept wireConfigName.
    const catalog = {
      current: () => [{ id: 'Doubao-Seed-Code', name: 'Seed-Code', input: ['text'] as ('text' | 'image')[] }],
    }
    const resolver = (id: string): string | undefined => (id === 'Doubao-Seed-Code' ? 'Doubao_1_6' : undefined)
    const result = await new TraeSoloBridge(upstream, catalog, resolver).chatStream(JSON.stringify({
      model: 'Doubao-Seed-Code', messages: [{ role: 'user', content: '1+1' }],
    }))
    expect(result.ok).toBe(true)
    expect((JSON.parse(forwarded) as Record<string, unknown>)['model']).toBe('Doubao_1_6')
  })

  it('preserves only a reasoning effort advertised by the selected model', async () => {
    let forwarded = ''
    const upstream: TraeUpstreamClient = {
      async chatStream(bodyJson) {
        forwarded = bodyJson
        return { ok: true, response: traeStream(['event: done\ndata: {"finish_reason":"stop"}\n\n']) }
      },
    }
    const catalog = {
      current: () => [{ id: 'qwen', name: 'Qwen', reasoningEfforts: { low: 'light', high: 'high', xhigh: 'extra_high' } }],
    }
    await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'qwen', reasoning_effort: 'high', messages: [{ role: 'user', content: 'hi' }],
    }))
    expect(JSON.parse(forwarded)).toHaveProperty('reasoning_effort', 'high')
    await new TraeSoloBridge(upstream, catalog).chatStream(JSON.stringify({
      model: 'qwen', reasoning_effort: 'medium', messages: [{ role: 'user', content: 'hi' }],
    }))
    expect(JSON.parse(forwarded)).not.toHaveProperty('reasoning_effort')
  })

  it('passes through upstream failures', async () => {
    const upstream: TraeUpstreamClient = { async chatStream() { return { ok: false, status: 402, kind: 'hard_credit', message: 'quota' } } }
    const result = await new TraeSoloBridge(upstream).chatStream('{}')
    expect(result).toEqual({ ok: false, status: 402, kind: 'hard_credit', message: 'quota' })
  })
})
