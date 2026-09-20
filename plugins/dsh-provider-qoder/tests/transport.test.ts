import test from 'node:test'
import assert from 'node:assert/strict'
import { createUserMessage, type GenerateOptions } from '@deepseek-ai/dsh-llm'
import { QoderLlmError } from '../src/qoder/errors.ts'
import { createQoderTransport } from '../src/qoder/transport/index.ts'

const catalog = JSON.stringify({ assistant: [{ key: 'cmodel', enable: true, display_name: 'Cantus' }] })

test('QoderTransport shares concurrent model discovery', async () => {
  let catalogCalls = 0
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-shared'),
    resolveMachineId: () => 'machine-test',
    fetch: (async (input: RequestInfo | URL): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-shared' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-shared' }))
      if (url.includes('/model/list')) {
        catalogCalls++
        await new Promise(resolve => setTimeout(resolve, 5))
        return new Response(catalog)
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  const [first, second] = await Promise.all([
    transport.discoverModels(),
    transport.discoverModels(),
  ])
  assert.equal(catalogCalls, 1)
  assert.equal(first, second)
})

test('QoderTransport retries an idempotent model discovery once', async () => {
  let catalogCalls = 0
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-retry'),
    resolveMachineId: () => 'machine-test',
    fetch: (async (input: RequestInfo | URL): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-retry' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-retry' }))
      if (url.includes('/model/list')) {
        catalogCalls++
        return catalogCalls === 1 ? new Response('', { status: 503 }) : new Response(catalog)
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  const models = await transport.discoverModels()
  assert.equal(catalogCalls, 2)
  assert.equal(models[0]?.id, 'cmodel')
})

test('QoderTransport aborts a shared discovery only after its last waiter leaves', async () => {
  let stallCatalog = false
  let upstreamAborted = false
  let notifyStarted: (() => void) | undefined
  const started = new Promise<void>(resolve => { notifyStarted = resolve })
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-shared'),
    resolveMachineId: () => 'machine-test',
    fetch: (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-shared' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-shared' }))
      if (url.includes('/model/list') && !stallCatalog) return new Response(catalog)
      if (url.includes('/model/list')) {
        notifyStarted?.()
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            upstreamAborted = true
            reject(new DOMException('aborted', 'AbortError'))
          }, { once: true })
        })
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  await transport.discoverModels()
  stallCatalog = true
  const firstController = new AbortController()
  const secondController = new AbortController()
  const first = transport.discoverModels(firstController.signal)
  const second = transport.discoverModels(secondController.signal)
  await started

  firstController.abort()
  await assert.rejects(first, (error: Error) => error instanceof QoderLlmError && error.code === 'ABORTED')
  assert.equal(upstreamAborted, false)

  secondController.abort()
  await assert.rejects(second, (error: Error) => error instanceof QoderLlmError && error.code === 'ABORTED')
  assert.equal(upstreamAborted, true)
})

test('QoderTransport separates response-header timeout from stream idle timeout', async () => {
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-timeout'),
    resolveMachineId: () => 'machine-test',
    responseHeaderTimeoutMs: 5,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-timeout' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-timeout' }))
      if (url.includes('/agent_chat_generation')) {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('timeout', 'AbortError')), { once: true })
        })
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })
  const request: GenerateOptions = {
    provider: 'dsh-provider-qoder',
    model: 'cmodel',
    messages: [createUserMessage({ content: [{ type: 'text', text: 'Hello' }], source: { kind: 'user' } })],
  }

  await assert.rejects(async () => {
    for await (const _chunk of transport.stream(request)) continue
  }, (error: Error) => (
    error instanceof QoderLlmError
    && error.code === 'TIMEOUT'
    && /response header/u.test(error.message)
  ))
})

const visionModel = {
  id: 'cmodel',
  name: 'Cantus Vision',
  supportsImages: true,
}

const imageRef = {
  attachmentId: 'sha256:image-1' as never,
  mediaType: 'image/png' as const,
  bytes: 3,
  width: 1,
  height: 1,
}

function transportAttachments() {
  return {
    imageLimits: {
      maxImageBytes: 5 * 1024 * 1024,
      maxImagesPerMessage: 20,
      maxMessageImageBytes: 100 * 1024 * 1024,
      maxImagePixels: 40_000_000,
      maxImageDimension: 2_000,
      mediaTypes: ['image/png', 'image/jpeg', 'image/webp', 'image/gif'] as const,
    },
    async readImageRequest(attachment: unknown) {
      return {
        variantId: 'sha256:variant-1',
        attachment,
        data: new Uint8Array([1, 2, 3]),
        mediaType: 'image/png',
        bytes: 3,
        width: 1,
        height: 1,
        depth: 'uchar',
        space: 'srgb',
        hasAlpha: true,
      }
    },
  } as never
}

function imageRequest(): GenerateOptions {
  return {
    provider: 'dsh-provider-qoder',
    model: 'cmodel',
    messages: [createUserMessage({
      content: [{ type: 'text', text: 'Look' }, { type: 'image', attachment: imageRef }],
      source: { kind: 'user' },
    })],
  } as GenerateOptions
}

test('QoderTransport publishes images to the center service before streaming', async () => {
  let uploads = 0
  let chatBody = ''
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-image'),
    resolveMachineId: () => 'machine-test',
    attachments: transportAttachments(),
    fetch: (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-image' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-image' }))
      if (url.includes('/image/upload')) {
        uploads++
        return new Response(JSON.stringify({ result: { oss_url: 'https://oss.qoder.sh/x.png' } }))
      }
      if (url.includes('/agent_chat_generation')) {
        chatBody = String(init?.body ?? '')
        return new Response('data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } })
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  for await (const _chunk of transport.stream(imageRequest(), visionModel)) continue
  assert.equal(uploads, 1)
  // The chat body is WAF-encoded, so assert on size: an inlined base64 image
  // would make it far larger than a short published URL.
  assert.ok(chatBody.length > 0)
  assert.ok(chatBody.length < 4_000, `chat body unexpectedly large: ${chatBody.length}`)
})

test('QoderTransport rejects images for a non-vision model before authenticating', async () => {
  let patCalls = 0
  let fetchCalls = 0
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => {
      patCalls++
      return Promise.resolve('pt-none')
    },
    resolveMachineId: () => 'machine-test',
    attachments: transportAttachments(),
    fetch: (async (): Promise<Response> => {
      fetchCalls++
      return new Response('{}')
    }) as typeof fetch,
  })

  await assert.rejects(async () => {
    for await (const _chunk of transport.stream(imageRequest(), { id: 'cmodel', name: 'Text only' })) continue
  }, (error: Error) => (
    error instanceof QoderLlmError && error.code === 'UNSUPPORTED_CONTENT'
  ))
  assert.equal(patCalls, 0)
  assert.equal(fetchCalls, 0)
})

test('QoderTransport still streams when center image publication fails', async () => {
  let chatCalls = 0
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: () => Promise.resolve('pt-degrade'),
    resolveMachineId: () => 'machine-test',
    attachments: transportAttachments(),
    logger: { warn: () => {} },
    fetch: (async (input: RequestInfo | URL): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-degrade' }))
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-degrade' }))
      if (url.includes('/image/upload')) return new Response('', { status: 500 })
      if (url.includes('/agent_chat_generation')) {
        chatCalls++
        return new Response('data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } })
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  for await (const _chunk of transport.stream(imageRequest(), visionModel)) continue
  assert.equal(chatCalls, 1)
})

test('QoderTransport signs chat with the job token refreshed during image publication', async () => {
  let exchanges = 0
  let uploads = 0
  let chatUser = ''
  const transport = createQoderTransport({
    region: 'global',
    resolvePat: async () => 'pt-refresh',
    resolveMachineId: () => 'machine-test',
    attachments: transportAttachments(),
    fetch: (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input)
      if (url.includes('/jobToken/exchange')) {
        exchanges++
        return new Response(JSON.stringify({ token: `jt-${exchanges}` }))
      }
      if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: `user-${exchanges}` }))
      if (url.includes('/image/upload')) {
        uploads++
        return uploads === 1
          ? new Response('', { status: 401 })
          : new Response(JSON.stringify({ url: 'https://oss.qoder.sh/x.png' }))
      }
      if (url.includes('/agent_chat_generation')) {
        chatUser = new Headers(init?.headers).get('Cosy-User')!
        return new Response('data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } })
      }
      throw new Error(`unexpected URL: ${url}`)
    }) as typeof fetch,
  })

  for await (const _chunk of transport.stream(imageRequest(), visionModel)) continue
  assert.equal(exchanges, 2)
  assert.equal(uploads, 2)
  assert.equal(chatUser, 'user-2')
})
