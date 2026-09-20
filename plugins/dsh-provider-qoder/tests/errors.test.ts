import test from 'node:test'
import assert from 'node:assert/strict'
import { LlmError } from '@deepseek-ai/dsh-llm'
import { QoderLlmError, qoderHttpError, retryAfterMs } from '../src/qoder/errors.ts'

test('QoderLlmError is a structured DSH LlmError', () => {
  const error = new QoderLlmError('unavailable', 'SERVER', { status: 503 })
  assert.ok(error instanceof LlmError)
  assert.deepEqual(error.failure, { message: 'unavailable', code: 'SERVER', status: 503 })
})

test('qoderHttpError maps HTTP status classes to DSH error codes', () => {
  const cases = [
    [400, 'INVALID_REQUEST'],
    [401, 'AUTH'],
    [403, 'AUTH'],
    [408, 'TIMEOUT'],
    [429, 'RATE_LIMIT'],
    [500, 'SERVER'],
    [503, 'SERVER'],
  ] as const
  for (const [status, code] of cases) {
    const error = qoderHttpError(`HTTP ${status}`, new Response(null, { status }))
    assert.equal(error.code, code)
    assert.equal(error.failure.status, status)
  }
})

test('retryAfterMs accepts delay-seconds and future HTTP dates', () => {
  const now = Date.parse('2026-09-03T00:00:00Z')
  assert.equal(retryAfterMs('3', now), 3000)
  assert.equal(retryAfterMs('Wed, 03 Sep 2026 00:00:05 GMT', now), 5000)
  assert.equal(retryAfterMs('0', now), undefined)
  assert.equal(retryAfterMs('invalid', now), undefined)
  assert.equal(retryAfterMs('Wed, 02 Sep 2026 00:00:00 GMT', now), undefined)
})

test('qoderHttpError preserves an upstream request id', () => {
  const error = qoderHttpError('unavailable', {
    status: 503,
    headers: new Headers({ 'x-request-id': 'request-42' }),
  })
  assert.equal(error.failure.requestId, 'request-42')
})
