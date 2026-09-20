import test from 'node:test'
import assert from 'node:assert/strict'
import { QoderLlmError } from '../src/qoder/errors.ts'
import { fetchQoderModels } from '../src/qoder/transport/catalog-reader.ts'
import {
  hasSameQoderDiscoveryMetadata,
  mergeQoderDiscoveryMetadata,
  normalizeQoderModels,
} from '../src/qoder/catalog.ts'

const payload = {
  chat: [{ key: 'chat-only', enable: true }],
  assistant: [
    { key: 'disabled', enable: false, display_name: 'Disabled' },
    {
      key: 'reasoner',
      enable: true,
      display_name: 'Reasoner',
      max_input_tokens: 100_000,
      max_output_tokens: 16_384,
      source: 'premium',
      price_factor: 0.5,
      is_vl: true,
      is_reasoning: true,
      thinking_config: {
        enabled: {
          efforts: {
            high: { description: 'Deep reasoning', is_default: true },
            custom: { description: 'Provider-specific reasoning' },
            low: { description: 'Fast reasoning' },
          },
        },
      },
      context_config: {
        small: { token_count: 100_000, is_default: true },
        large: { token_count: 400_000 },
      },
    },
    { key: 'reasoner', enable: true, display_name: 'Duplicate' },
  ],
}

test('assistant is required even when chat advertises enabled models', async () => {
  for (const assistant of [undefined, null, {}, [], [{ key: 'disabled', enable: false }]]) {
    const body = { chat: [{ key: 'chat-only', enable: true }], assistant }
    assert.deepEqual(normalizeQoderModels(body), [])
    await assert.rejects(() => fetchQoderModels({
      userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
    }, { fetch: (async () => new Response(JSON.stringify(body))) as typeof fetch }), /no enabled models/u)
  }
})

test('context defaults and fallback capacities stay separate from maximum capacity', () => {
  const cases = [
    { context: { small: { token_count: 200_000, is_default: true }, large: { token_count: 1_000_000 } }, expected: 200_000, conflicts: 0 },
    { context: { large: { token_count: 1_000_000 } }, expected: 180_000, conflicts: 0 },
    { context: { small: { token_count: 200_000, is_default: true }, large: { token_count: 1_000_000, is_default: true } }, expected: 180_000, conflicts: 1 },
    { context: { invalid: { token_count: -1, is_default: true }, large: { token_count: 1_000_000 } }, expected: 180_000, conflicts: 0 },
  ]
  for (const { context, expected, conflicts: expectedConflicts } of cases) {
    const conflicts: string[] = []
    const [model] = normalizeQoderModels({ assistant: [{
      key: 'model', enable: true, max_input_tokens: 180_000, context_config: context,
    }] }, conflict => conflicts.push(conflict))
    assert.equal(model.contextWindow, expected)
    assert.equal(model.maxContextWindow, 1_000_000)
    assert.equal(conflicts.length, expectedConflicts)
  }
  const [fallback] = normalizeQoderModels({ assistant: [{ key: 'model', enable: true }] })
  assert.equal(fallback.contextWindow, 180_000)
  assert.equal(fallback.maxTokens, 32_768)
})

test('thinking state follows a unique explicit default and otherwise the reasoning flag', () => {
  for (const flag of [false, true]) {
    for (const [thinking, expected] of [
      [undefined, flag],
      [{}, flag],
      [{ enabled: {} }, flag],
      [{ enabled: { is_default: true } }, true],
      [{ disabled: { is_default: true } }, false],
      [{ enabled: { is_default: true }, disabled: { is_default: true } }, flag],
    ] as const) {
      const conflicts: string[] = []
      const [model] = normalizeQoderModels({ assistant: [{
        key: 'model', enable: true, is_reasoning: flag, thinking_config: thinking,
      }] }, conflict => conflicts.push(conflict))
      assert.equal(model.isReasoning, expected)
      assert.equal(model.reasoningEfforts, undefined)
      assert.equal(model.supportsEffort, false)
      assert.equal(conflicts.length, thinking && 'disabled' in thinking && 'enabled' in thinking ? 1 : 0)
    }
  }
})

test('price factors preserve zero without inferring prices from free or promotion flags', () => {
  for (const [price, expected] of [[0, 0], [0.5, 0.5], [-1, undefined], [Infinity, undefined], [NaN, undefined]] as const) {
    const [model] = normalizeQoderModels({ assistant: [{
      key: 'model', enable: true, price_factor: price, is_free: true,
      promotion: { active: true, discount_factor: 0.2 },
    }] })
    assert.equal(model.priceFactor, expected)
  }
})

test('rediscovery caps old input budgets and preserves smaller budgets', () => {
  const discovered = normalizeQoderModels({ assistant: [{
    key: 'model', enable: true, context_config: {
      small: { token_count: 200_000, is_default: true }, large: { token_count: 1_000_000 },
    },
  }] })
  for (const budget of [undefined, 100_000, 1_000_000]) {
    const configured = [{ id: 'model', name: 'Model', contextWindow: budget }]
    const merged = mergeQoderDiscoveryMetadata(configured, discovered)
    assert.equal(merged[0].contextWindow, budget === 100_000 ? 100_000 : 200_000)
    assert.equal(merged[0].maxContextWindow, 1_000_000)
    assert.equal(hasSameQoderDiscoveryMetadata(merged, mergeQoderDiscoveryMetadata(merged, discovered)), true)
    assert.equal(hasSameQoderDiscoveryMetadata(merged, [{ ...merged[0], contextWindow: 50_000 }]), false)
  }
})

test('catalog conflict diagnostics contain only conflict kinds', async () => {
  const warnings: unknown[] = []
  await fetchQoderModels({
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }, {
    logger: { warn: (...args) => { warnings.push(args) } },
    fetch: (async () => new Response(JSON.stringify({ assistant: [{
      key: 'model', enable: true,
      strategies: [{ whitelist: ['private-subscriber'] }],
      thinking_config: { enabled: { is_default: true }, disabled: { is_default: true } },
    }] }))) as typeof fetch,
  })
  assert.deepEqual(warnings, [[
    '[Qoder Models] Conflicting catalog defaults; using fallback', { conflict: 'thinking-defaults' },
  ]])
})

test('normalizeQoderModels keeps enabled unique models and their transport metadata', () => {
  assert.deepEqual(normalizeQoderModels(payload), [{
    id: 'reasoner',
    name: 'Reasoner',
    contextWindow: 100_000,
    maxContextWindow: 400_000,
    maxTokens: 16_384,
    source: 'premium',
    isReasoning: true,
    supportsEffort: true,
    supportsImages: true,
    reasoningEfforts: [
      { id: 'low', name: 'low', description: 'Fast reasoning' },
      { id: 'high', name: 'high', description: 'Deep reasoning' },
      { id: 'custom', name: 'custom', description: 'Provider-specific reasoning' },
    ],
    defaultReasoningEffort: 'high',
    priceFactor: 0.5,
    contextOptions: {
      small: { tokenCount: 100_000, isDefault: true },
      large: { tokenCount: 400_000 },
    },
  }])
})

test('mergeQoderDiscoveryMetadata restores effort and rate data stripped by generic discovery', () => {
  const configured = [{
    id: 'reasoner',
    name: 'Chosen name',
    contextWindow: 200_000,
    maxTokens: 8_192,
  }, {
    id: 'manual',
    name: 'Manual model',
    reasoningEfforts: [{ id: 'legacy', name: 'legacy' }],
  }]
  const discovered = normalizeQoderModels(payload)

  const enriched = mergeQoderDiscoveryMetadata(configured, discovered)
  assert.deepEqual(enriched, [{
    id: 'reasoner',
    name: 'Chosen name',
    contextWindow: 100_000,
    maxContextWindow: 400_000,
    maxTokens: 8_192,
    source: 'premium',
    isReasoning: true,
    supportsEffort: true,
    supportsImages: true,
    reasoningEfforts: [
      { id: 'low', name: 'low', description: 'Fast reasoning' },
      { id: 'high', name: 'high', description: 'Deep reasoning' },
      { id: 'custom', name: 'custom', description: 'Provider-specific reasoning' },
    ],
    defaultReasoningEffort: 'high',
    priceFactor: 0.5,
    contextOptions: {
      small: { tokenCount: 100_000, isDefault: true },
      large: { tokenCount: 400_000 },
    },
  }, {
    id: 'manual',
    name: 'Manual model',
    reasoningEfforts: [{ id: 'legacy', name: 'legacy' }],
  }])
  assert.equal(hasSameQoderDiscoveryMetadata(configured, enriched), false)
  assert.equal(hasSameQoderDiscoveryMetadata(enriched, enriched), true)
})

test('fetchQoderModels calls the encoded Global catalog with COSY authentication', async () => {
  let request: { url: string; init?: RequestInit } | undefined
  const logs: Array<{ message: string; details: unknown }> = []
  const models = await fetchQoderModels({
    userID: 'user-1',
    authToken: 'job-token',
    name: 'Subscriber',
    email: 'subscriber@example.com',
    machineID: 'machine-1',
  }, {
    logger: {
      debug: (message, details) => { logs.push({ message, details }) },
    },
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      request = { url: String(input), init }
      return new Response(JSON.stringify(payload))
    }) as typeof fetch,
  })

  assert.equal(models[0]?.id, 'reasoner')
  assert.equal(request?.url, 'https://api3.qoder.sh/algo/api/v2/model/list?Encode=1')
  assert.equal(request?.init?.method, 'GET')
  const headers = request?.init?.headers as Record<string, string>
  assert.match(headers.Authorization, /^Bearer COSY\./u)
  assert.equal(headers['Cosy-Sigpath'], '/api/v2/model/list')
  assert.equal(typeof (logs[1]?.details as { durationMs?: unknown }).durationMs, 'number')
  assert.deepEqual(logs.map((entry) => {
    if (entry.message !== '[Qoder Models] Catalog request completed') return entry
    const { durationMs: _, ...details } = entry.details as Record<string, unknown>
    return { ...entry, details }
  }), [
    {
      message: '[Qoder Models] Requesting model catalog',
      details: { url: 'https://api3.qoder.sh/algo/api/v2/model/list?Encode=1' },
    },
    {
      message: '[Qoder Models] Catalog request completed',
      details: { url: 'https://api3.qoder.sh/algo/api/v2/model/list?Encode=1', status: 200 },
    },
  ])
})

test('fetchQoderModels rejects malformed and empty catalogs', async () => {
  await assert.rejects(() => fetchQoderModels({
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }, { fetch: (async () => new Response('{')) as typeof fetch }), /invalid JSON/u)
  await assert.rejects(() => fetchQoderModels({
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }, { fetch: (async () => new Response(JSON.stringify({ assistant: [] }))) as typeof fetch }), /no enabled models/u)
})

test('fetchQoderModels classifies HTTP and network failures', async () => {
  const credentials = {
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }
  await assert.rejects(() => fetchQoderModels(credentials, {
    fetch: (async () => new Response('', { status: 503 })) as typeof fetch,
  }), (error: Error) => (
    error instanceof QoderLlmError
    && error.code === 'SERVER'
    && error.failure.status === 503
  ))
  await assert.rejects(() => fetchQoderModels(credentials, {
    fetch: (async () => { throw new TypeError('fetch failed') }) as typeof fetch,
  }), (error: Error) => error instanceof QoderLlmError && error.code === 'TRANSPORT')
})

test('fetchQoderModels applies its own deadline and normalizes body-read cancellation', async () => {
  const credentials = {
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }
  await assert.rejects(() => fetchQoderModels(credentials, {
    timeoutMs: 5,
    fetch: (async (_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('timeout', 'AbortError')), { once: true })
    })) as typeof fetch,
  }), (error: Error) => error instanceof QoderLlmError && error.code === 'TIMEOUT')

  const caller = new AbortController()
  await assert.rejects(() => fetchQoderModels(credentials, {
    signal: caller.signal,
    fetch: (async (_input: RequestInfo | URL, init?: RequestInit) => new Response(new ReadableStream<Uint8Array>({
      start(controller) {
        init?.signal?.addEventListener('abort', () => controller.error(new DOMException('aborted', 'AbortError')))
        queueMicrotask(() => caller.abort())
      },
    }))) as typeof fetch,
  }), (error: Error) => error instanceof QoderLlmError && error.code === 'ABORTED')
})

test('fetchQoderModels rejects oversized catalog responses', async () => {
  await assert.rejects(() => fetchQoderModels({
    userID: 'user-1', authToken: 'job-token', name: '', email: '', machineID: 'machine-1',
  }, {
    fetch: (async () => new Response('', {
      headers: { 'content-length': String(3 * 1024 * 1024) },
    })) as typeof fetch,
  }), (error: Error) => error instanceof QoderLlmError && error.code === 'MALFORMED_RESPONSE')
})
