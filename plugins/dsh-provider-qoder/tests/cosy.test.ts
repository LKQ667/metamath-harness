import test from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { buildAuthHeaders, computeSigPath } from '../src/qoder/transport/wire/cosy.ts'
import { getQoderChatUrl } from '../src/qoder/transport/endpoints.ts'
import { getMachineId } from '../src/qoder/transport/machine-id.ts'

test('computeSigPath strips the /algo prefix', () => {
  assert.equal(computeSigPath('https://api3.qoder.sh/algo/api/v2/service'), '/api/v2/service')
})

test('getMachineId accepts an isolated storage location', () => {
  const path = join(tmpdir(), `qoder-machine-${crypto.randomUUID()}`, 'machine_id')
  const machineId = getMachineId([path])
  assert.ok(machineId.length > 0)
  assert.equal(getMachineId([path]), machineId)
})

test('buildAuthHeaders creates the required bounded COSY headers', () => {
  const body = Buffer.from('encoded-body')
  const headers = buildAuthHeaders(body, getQoderChatUrl(), {
    userID: 'user-123',
    authToken: 'jt-token',
    name: 'User',
    email: 'user@example.com',
    machineID: 'machine-123',
  })
  assert.ok(headers.Authorization.startsWith('Bearer COSY.'))
  assert.equal(headers['Cosy-User'], 'user-123')
  assert.equal(headers['Cosy-Bodylength'], String(body.length))
  assert.equal(headers['Cosy-Sigpath'], '/api/v2/service/pro/sse/agent_chat_generation')
})
