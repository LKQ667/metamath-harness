import test from 'node:test'
import assert from 'node:assert/strict'
import {
  logParsedResponse,
  redactLogPayload,
  redactLogValue,
} from '../src/qoder/transport/logging.ts'

test('Qoder diagnostics redact credentials and subscriber identifiers while preserving useful fields', () => {
  const redacted = redactLogValue({
    id: 'user-123456',
    email: 'subscriber@example.com',
    authorization: 'Bearer jt-secret-token',
    nested: {
      personal_token: 'pt-personal-secret',
      unit: 'credits',
      remaining: 42,
    },
  })
  const output = JSON.stringify(redacted)
  assert.doesNotMatch(output, /user-123456|subscriber@example\.com|jt-secret-token|pt-personal-secret/)
  assert.match(output, /credits/)
  assert.match(output, /42/)
})

test('Qoder diagnostics redact token-like values in JSON and plain-text payloads', () => {
  assert.doesNotMatch(JSON.stringify(redactLogPayload('{"token":"jt-json-secret"}')), /jt-json-secret/)
  assert.doesNotMatch(String(redactLogPayload('upstream rejected pt-plain-secret')), /pt-plain-secret/)
})

test('Qoder diagnostics preserve nested fetch failure codes while redacting causes', () => {
  const cause = Object.assign(new Error('connect timeout pt-connect-secret'), {
    code: 'UND_ERR_CONNECT_TIMEOUT',
  })
  assert.deepEqual(redactLogValue(new TypeError('fetch failed', { cause })), {
    name: 'TypeError',
    message: 'fetch failed',
    cause: {
      name: 'Error',
      message: 'connect timeout [REDACTED]',
      code: 'UND_ERR_CONNECT_TIMEOUT',
    },
  })
})

test('Qoder diagnostics retain aggregate connection failures and redact nested details', () => {
  const failures = [
    Object.assign(new Error('connection reset'), { code: 'ECONNRESET' }),
    Object.assign(new Error('DNS lookup failed'), { code: 'EAI_AGAIN' }),
  ]
  const error = new TypeError('fetch failed', {
    cause: new AggregateError(failures, 'connection attempts failed', {
      cause: { authorization: 'Bearer private-value', userId: 'user-123456' },
    }),
  })
  const output = JSON.stringify(redactLogValue(error))
  assert.match(output, /ECONNRESET/)
  assert.match(output, /EAI_AGAIN/)
  assert.doesNotMatch(output, /private-value|user-123456/)
})

test('Qoder diagnostics bound cyclic causes and aggregate error collections', () => {
  const error = new Error('cyclic failure')
  error.cause = error
  assert.match(JSON.stringify(redactLogValue(error)), /\[TRUNCATED\]/)
  const aggregate = new AggregateError(Array.from({ length: 100 }, () => error), 'many failures')
  const redacted = redactLogValue(aggregate) as { errors: unknown[] }
  assert.equal(redacted.errors.length, 50)
  assert.match(JSON.stringify(redacted), /\[TRUNCATED\]/)
})

test('parsed response logging uses one event shape and redacts its result', () => {
  const entries: Array<{ message: string; details: unknown }> = []
  logParsedResponse({
    debug: (message, details) => entries.push({ message, details }),
  }, 'auth.exchange', {
    token: 'jt-parsed-secret',
    expires_in: 3_600_000,
  })

  assert.equal(entries[0]?.message, '[Qoder Response] Parsed')
  assert.deepEqual(entries[0]?.details, {
    operation: 'auth.exchange',
    result: {
      token: '[REDACTED]',
      expires_in: 3_600_000,
    },
  })
})
