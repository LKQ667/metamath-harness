import test from 'node:test'
import assert from 'node:assert/strict'
import { Context } from '@deepseek-ai/cordis'
import { WebError, type WebSearchProvider, type WebSearchResult } from '@deepseek-ai/dsh-web'
import { getQoderWebSearchUrl, qoderWebSearchPath } from '../src/qoder/transport/endpoints.ts'
import { QoderSearchClient } from '../src/qoder/transport/search.ts'
import { QoderSearchProvider, QODER_SEARCH_PROVIDER_ID } from '../src/dsh/search-provider.ts'
import { QODER_PROVIDER_ID } from '../src/dsh/provider.ts'
import type { CosyCredentials } from '../src/qoder/transport/wire/cosy.ts'

import { qoderEncodeBody } from '../src/qoder/transport/wire/encoding.ts'

const testCredentials: CosyCredentials = {
  userID: 'user-search-1',
  authToken: 'token-search-1',
  name: 'Search Tester',
  email: 'tester@example.com',
  machineID: 'mach-search-1',
}

test('getQoderWebSearchUrl targets center oneSearch endpoint for global and china', () => {
  assert.equal(getQoderWebSearchUrl('global'), 'https://center.qoder.sh/algo/api/v1/webSearch/oneSearch?Encode=1')
  assert.equal(getQoderWebSearchUrl('china'), 'https://gateway.qoder.com.cn/algo/api/v1/webSearch/oneSearch?Encode=1')
  assert.equal(qoderWebSearchPath, '/api/v1/webSearch/oneSearch')
})

test('QoderSearchClient signs requests and parses search results', async () => {
  let capturedUrl: string | undefined
  let capturedInit: RequestInit | undefined

  const mockResponse = {
    errorCode: 0,
    errorMsg: 'ok',
    requestId: 'req-123',
    pageItems: [
      {
        title: 'DeepSeek Official',
        link: 'https://deepseek.com',
        snippet: 'DeepSeek LLM and research.',
        publishedAt: '2026-01-01',
      },
      {
        title: 'Duplicate URL',
        link: 'https://deepseek.com',
        snippet: 'Duplicate snippet.',
      },
      {
        title: 'Empty Link',
        link: '',
        snippet: 'Ignored item',
      },
    ],
  }

  const client = new QoderSearchClient({
    region: 'global',
    resolveCredentials: async () => testCredentials,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = String(input)
      capturedInit = init
      return new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as typeof fetch,
  })

  const result = await client.search({ query: 'DeepSeek AI' })

  assert.equal(capturedUrl, 'https://center.qoder.sh/algo/api/v1/webSearch/oneSearch?Encode=1')
  assert.equal(capturedInit?.method, 'POST')

  const headers = capturedInit?.headers as Record<string, string>
  assert.ok(headers['Authorization']?.startsWith('Bearer COSY.'))
  assert.equal(headers['Content-Type'], 'application/json')
  assert.equal(headers['Accept-Encoding'], 'identity')
  assert.equal(headers['Cosy-User'], 'user-search-1')

  const expectedOuterBody = JSON.stringify({
    payload: JSON.stringify({
      query: 'DeepSeek AI',
      timeRange: 'NoLimit',
      contents: {
        mainText: false,
        markdownText: false,
        summary: false,
      },
    }),
    encodeVersion: '1',
  })
  assert.equal(capturedInit?.body, qoderEncodeBody(expectedOuterBody))

  // Duplicates and empty links should be handled
  assert.equal(result.sources.length, 1)
  assert.equal(result.sources[0].url, 'https://deepseek.com')
  assert.equal(result.sources[0].title, 'DeepSeek Official')
  assert.equal(result.sources[0].snippet, 'DeepSeek LLM and research.')
  assert.equal(result.sources[0].publishedAt, '2026-01-01')
  assert.equal(result.truncated, false)
})

test('QoderSearchClient refetches credentials and retries once on HTTP 401', async () => {
  let callCount = 0
  let refreshCalled = false

  const client = new QoderSearchClient({
    region: 'china',
    resolveCredentials: async () => testCredentials,
    refreshCredentials: async () => {
      refreshCalled = true
      return { ...testCredentials, authToken: 'new-refreshed-token' }
    },
    fetch: (async () => {
      callCount++
      if (callCount === 1) {
        return new Response('Unauthorized', { status: 401, statusText: 'Unauthorized' })
      }
      return new Response(JSON.stringify({
        errorCode: 0,
        pageItems: [{ title: 'Success', link: 'https://example.com', snippet: 'Success snippet' }],
      }), { status: 200 })
    }) as typeof fetch,
  })

  const result = await client.search({ query: 'test retry' })
  assert.equal(callCount, 2)
  assert.equal(refreshCalled, true)
  assert.equal(result.sources.length, 1)
  assert.equal(result.sources[0].title, 'Success')
})

test('QoderSearchClient throws WebError on backend error code', async () => {
  const client = new QoderSearchClient({
    resolveCredentials: async () => testCredentials,
    fetch: (async () => new Response(JSON.stringify({
      errorCode: 4001,
      errorMsg: 'quota exhausted',
    }), { status: 200 })) as typeof fetch,
  })

  await assert.rejects(
    () => client.search({ query: 'error query' }),
    (err: unknown) => err instanceof WebError && err.code === 'WEB_PROVIDER_ERROR' && err.message.includes('4001'),
  )
})

test('QoderSearchClient honors cancellation signal with WEB_ABORTED', async () => {
  const controller = new AbortController()
  controller.abort()

  const client = new QoderSearchClient({
    resolveCredentials: async () => testCredentials,
    fetch: (async () => new Response('{}')) as typeof fetch,
  })

  await assert.rejects(
    () => client.search({ query: 'aborted query' }, controller.signal),
    (err: unknown) => err instanceof WebError && err.code === 'WEB_ABORTED',
  )
})

test('QoderSearchProvider routes based on initiator agent provider and mode', async () => {
  const ctx = new Context()
  let currentAgentProvider: string | undefined = QODER_PROVIDER_ID

  // Mock ctx.agents.currentInitiator()
  ;(ctx as unknown as Record<string, unknown>).agents = {
    currentInitiator: () => ({
      options: {
        provider: currentAgentProvider,
      },
    }),
  }

  let qoderSearchCalled = false
  const mockSearchClient = {
    search: async () => {
      qoderSearchCalled = true
      return { sources: [{ url: 'https://qoder.sh' }], truncated: false }
    },
  } as unknown as QoderSearchClient

  let fallbackSearchCalled = false
  const mockFallbackProvider: WebSearchProvider = {
    id: 'deepseek-official',
    available: () => true,
    search: async () => {
      fallbackSearchCalled = true
      return { sources: [{ url: 'https://deepseek.com' }], truncated: false }
    },
  }

  let mode: 'auto' | 'always' | 'disabled' = 'auto'

  const provider = new QoderSearchProvider({
    ctx,
    searchClient: mockSearchClient,
    getWebSearchMode: () => mode,
    fallbackProvider: mockFallbackProvider,
  })

  assert.equal(provider.id, QODER_SEARCH_PROVIDER_ID)
  assert.equal(provider.available(), true)

  // Case 1: mode='auto', agent is dsh-provider-qoder -> routes to Qoder
  currentAgentProvider = QODER_PROVIDER_ID
  qoderSearchCalled = false
  fallbackSearchCalled = false
  const res1 = await provider.search({ query: 'hello' })
  assert.equal(qoderSearchCalled, true)
  assert.equal(fallbackSearchCalled, false)
  assert.equal(res1.sources[0].url, 'https://qoder.sh')

  // Case 2: mode='auto', agent is deepseek-official -> delegates to fallback
  currentAgentProvider = 'deepseek-official'
  qoderSearchCalled = false
  fallbackSearchCalled = false
  const res2 = await provider.search({ query: 'hello' })
  assert.equal(qoderSearchCalled, false)
  assert.equal(fallbackSearchCalled, true)
  assert.equal(res2.sources[0].url, 'https://deepseek.com')

  // Case 3: mode='always', agent is deepseek-official -> still forces Qoder
  mode = 'always'
  currentAgentProvider = 'deepseek-official'
  qoderSearchCalled = false
  fallbackSearchCalled = false
  const res3 = await provider.search({ query: 'hello' })
  assert.equal(qoderSearchCalled, true)
  assert.equal(fallbackSearchCalled, false)
  assert.equal(res3.sources[0].url, 'https://qoder.sh')

  // Case 4: mode='disabled' -> unavailable and search throws
  mode = 'disabled'
  assert.equal(provider.available(), false)
  await assert.rejects(
    () => provider.search({ query: 'hello' }),
    (err: unknown) => err instanceof WebError && err.code === 'WEB_PROVIDER_UNAVAILABLE',
  )
})

test('QoderSearchProvider delegates to resolveTransport when configured', async () => {
  const ctx = new Context()
  ;(ctx as unknown as Record<string, unknown>).agents = {
    currentInitiator: () => ({
      options: {
        provider: QODER_PROVIDER_ID,
      },
    }),
  }

  let transportSearchCalled = false
  const fakeTransport = {
    searchWeb: async () => {
      transportSearchCalled = true
      return { sources: [{ url: 'https://transport.qoder.sh' }], truncated: false }
    },
  } as any

  const provider = new QoderSearchProvider({
    ctx,
    resolveTransport: () => fakeTransport,
    getWebSearchMode: () => 'auto',
  })

  const result = await provider.search({ query: 'test transport' })
  assert.equal(transportSearchCalled, true)
  assert.equal(result.sources[0].url, 'https://transport.qoder.sh')
})

test('QoderSearchProvider falls back to agentDefaultModel when currentInitiator is absent', async () => {
  const ctx = new Context()
  ;(ctx as unknown as Record<string, unknown>).agents = {
    currentInitiator: () => undefined,
  }
  ctx.provide('agentDefaultModel', {
    get: () => ({ provider: QODER_PROVIDER_ID, model: 'gfmodel' }),
  } as any)

  let qoderSearchCalled = false
  const fakeTransport = {
    searchWeb: async () => {
      qoderSearchCalled = true
      return { sources: [{ url: 'https://default-qoder.sh' }], truncated: false }
    },
  } as any

  const provider = new QoderSearchProvider({
    ctx,
    resolveTransport: () => fakeTransport,
    getWebSearchMode: () => 'auto',
  })

  const result = await provider.search({ query: 'test default model' })
  assert.equal(qoderSearchCalled, true)
  assert.equal(result.sources[0].url, 'https://default-qoder.sh')
})

test('QoderSearchProvider dynamically resolves fallback from web.searchProviders Map', async () => {
  const ctx = new Context()
  ;(ctx as unknown as Record<string, unknown>).agents = {
    currentInitiator: () => ({ options: { provider: 'deepseek-official' } }),
  }

  let fallbackCalled = false
  const deepseekFallback: WebSearchProvider = {
    id: 'deepseek-official',
    available: () => true,
    search: async () => {
      fallbackCalled = true
      return { sources: [{ url: 'https://fallback.deepseek.com' }], truncated: false }
    },
  }

  const searchProvidersMap = new Map<string, WebSearchProvider>()
  searchProvidersMap.set('deepseek-official', deepseekFallback)
  ctx.provide('web', { searchProviders: searchProvidersMap } as any)

  const provider = new QoderSearchProvider({
    ctx,
    getWebSearchMode: () => 'auto',
  })

  const result = await provider.search({ query: 'test dynamic fallback' })
  assert.equal(fallbackCalled, true)
  assert.equal(result.sources[0].url, 'https://fallback.deepseek.com')
})


