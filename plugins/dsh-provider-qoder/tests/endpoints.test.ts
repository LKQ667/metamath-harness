import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getQoderChatUrl,
  getQoderExchangeUrl,
  getQoderModelListUrl,
  getQoderUsageUrl,
  getQoderUserInfoUrl,
  getQoderUserPlanUrl,
  getQoderUserStatusUrl,
  resolveQoderEndpoints,
} from '../src/qoder/transport/endpoints.ts'
import { computeSigPath } from '../src/qoder/transport/wire/cosy.ts'

test('resolveQoderEndpoints returns expected endpoints for global and china', () => {
  const globalEndpoints = resolveQoderEndpoints('global')
  assert.equal(globalEndpoints.baseUrl, 'https://api3.qoder.sh/')
  assert.equal(globalEndpoints.openApiUrl, 'https://openapi.qoder.sh')

  const chinaEndpoints = resolveQoderEndpoints('china')
  assert.equal(chinaEndpoints.baseUrl, 'https://gateway.qoder.com.cn/')
  assert.equal(chinaEndpoints.openApiUrl, 'https://openapi.qoder.com.cn')

  // Defaults to global when unspecified
  assert.deepEqual(resolveQoderEndpoints(), globalEndpoints)
})

test('getQoderChatUrl builds chat URLs for global and china', () => {
  assert.equal(
    getQoderChatUrl('global'),
    'https://api3.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1',
  )
  assert.equal(
    getQoderChatUrl('china'),
    'https://gateway.qoder.com.cn/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1',
  )
  assert.equal(getQoderChatUrl(), getQoderChatUrl('global'))
})

test('getQoderModelListUrl builds model catalog URLs for global and china', () => {
  assert.equal(
    getQoderModelListUrl('global'),
    'https://api3.qoder.sh/algo/api/v2/model/list?Encode=1',
  )
  assert.equal(
    getQoderModelListUrl('china'),
    'https://gateway.qoder.com.cn/algo/api/v2/model/list?Encode=1',
  )
  assert.equal(getQoderModelListUrl(), getQoderModelListUrl('global'))
})

test('getQoderExchangeUrl builds token exchange URLs for global and china', () => {
  assert.equal(
    getQoderExchangeUrl('global'),
    'https://openapi.qoder.sh/api/v1/jobToken/exchange',
  )
  assert.equal(
    getQoderExchangeUrl('china'),
    'https://openapi.qoder.com.cn/api/v1/jobToken/exchange',
  )
  assert.equal(getQoderExchangeUrl(), getQoderExchangeUrl('global'))
})

test('getQoderUserInfoUrl builds userinfo URLs for global and china', () => {
  assert.equal(
    getQoderUserInfoUrl('global'),
    'https://openapi.qoder.sh/api/v1/userinfo',
  )
  assert.equal(
    getQoderUserInfoUrl('china'),
    'https://openapi.qoder.com.cn/api/v1/userinfo',
  )
  assert.equal(getQoderUserInfoUrl(), getQoderUserInfoUrl('global'))
})

test('getQoderUsageUrl builds quota usage URLs for global and china', () => {
  assert.equal(
    getQoderUsageUrl('global'),
    'https://openapi.qoder.sh/api/v2/quota/usage',
  )
  assert.equal(
    getQoderUsageUrl('china'),
    'https://openapi.qoder.com.cn/api/v2/quota/usage',
  )
  assert.equal(getQoderUsageUrl(), getQoderUsageUrl('global'))
})

test('computeSigPath strips the /algo prefix from China gateway chat URL', () => {
  const cnChatUrl = getQoderChatUrl('china')
  assert.equal(computeSigPath(cnChatUrl), '/api/v2/service/pro/sse/agent_chat_generation')
})

test('getQoderUserPlanUrl builds user plan URLs for global and china', () => {
  assert.equal(
    getQoderUserPlanUrl('global'),
    'https://openapi.qoder.sh/api/v2/user/plan',
  )
  assert.equal(
    getQoderUserPlanUrl('china'),
    'https://openapi.qoder.com.cn/api/v2/user/plan',
  )
  assert.equal(getQoderUserPlanUrl(), getQoderUserPlanUrl('global'))
})

test('getQoderUserStatusUrl builds user status URLs for global and china', () => {
  assert.equal(
    getQoderUserStatusUrl('global'),
    'https://openapi.qoder.sh/api/v3/user/status',
  )
  assert.equal(
    getQoderUserStatusUrl('china'),
    'https://openapi.qoder.com.cn/api/v3/user/status',
  )
  assert.equal(getQoderUserStatusUrl(), getQoderUserStatusUrl('global'))
})
