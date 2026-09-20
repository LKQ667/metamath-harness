import test from 'node:test'
import assert from 'node:assert/strict'
import { qoderEncodeBody } from '../src/qoder/transport/wire/encoding.ts'

test('qoderEncodeBody encodes ASCII strings deterministically', () => {
  const input = '{"test": "hello world"}'
  const encoded1 = qoderEncodeBody(input)
  const encoded2 = qoderEncodeBody(Buffer.from(input))

  assert.equal(typeof encoded1, 'string')
  assert.equal(encoded1, encoded2)
  assert.ok(encoded1.length > 0)
})

test('qoderEncodeBody handles padding characters correctly', () => {
  const input = 'a' // Base64 is "YQ==", should replace '=' with '$'
  const encoded = qoderEncodeBody(input)
  assert.ok(encoded.includes('$'))
})

test('qoderEncodeBody handles UTF-8 characters correctly', () => {
  const input = '{"message": "你好，世界"}'
  const encoded = qoderEncodeBody(input)
  assert.ok(encoded.length > 0)
})
