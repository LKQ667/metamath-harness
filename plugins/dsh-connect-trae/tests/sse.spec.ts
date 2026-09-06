import { describe, expect, it } from 'vitest'
import { decodeTraeEvent, SseDecoder } from '../src/sse.ts'

describe('SseDecoder', () => {
  it('handles arbitrary chunk boundaries, CRLF, comments and multiline data', () => {
    const decoder = new SseDecoder()
    expect(decoder.push('event: out')).toEqual([])
    expect(decoder.push('put\r\ndata: {"response":')).toEqual([])
    expect(decoder.push('"hello"}\r\n: keepalive\r\n\r\n')).toEqual([{ event: 'output', data: '{"response":"hello"}' }])
  })

  it('supports data-only SSE instead of silently dropping it', () => {
    const decoder = new SseDecoder()
    expect(decoder.push('data: {"response":"x"}\n\n')).toEqual([{ data: '{"response":"x"}' }])
    expect(decodeTraeEvent({ data: '{"response":"x"}' })).toEqual({ type: 'delta', text: 'x' })
  })

  it('decodes queue, reasoning, done and unknown events', () => {
    expect(decodeTraeEvent({ event: 'request_wait_in_queue', data: '{"position":2}' })).toEqual({ type: 'queue', position: 2 })
    expect(decodeTraeEvent({ event: 'progress_notice', data: '"Processing_123"' })).toEqual({ type: 'progress', notice: 'Processing_123' })
    expect(decodeTraeEvent({ event: 'output', data: '{"reasoning_content":"r","response":"t"}' })).toEqual({ type: 'delta', text: 't', reasoning: 'r' })
    expect(decodeTraeEvent({ event: 'done', data: '{"finish_reason":"stop"}' })).toEqual({ type: 'done', finishReason: 'stop' })
    expect(decodeTraeEvent({ data: '[DONE]' })).toEqual({ type: 'done', finishReason: 'stop' })
    expect(decodeTraeEvent({ event: 'other', data: 'plain' })).toEqual({ type: 'unknown', event: 'other', data: 'plain' })
  })

  it('flushes a final event without a trailing blank line', () => {
    const decoder = new SseDecoder()
    decoder.push('event: done\ndata: {"finish_reason":"stop"}')
    expect(decoder.finish()).toEqual([{ event: 'done', data: '{"finish_reason":"stop"}' }])
  })
})
