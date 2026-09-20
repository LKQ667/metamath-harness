import test from 'node:test'
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import type { RequestImageAttachment } from '@deepseek-ai/dsh-attachment'
import { QoderLlmError } from '../src/qoder/errors.ts'
import {
  buildQoderImageMultipart,
  QoderImageUploader,
  readQoderImageUrl,
} from '../src/qoder/transport/image-upload.ts'
import { getQoderImageUploadUrl } from '../src/qoder/transport/endpoints.ts'
import { computeSigPath } from '../src/qoder/transport/wire/cosy.ts'
import type { CosyCredentials } from '../src/qoder/transport/wire/cosy.ts'

const credentials: CosyCredentials = {
  userID: 'user-1',
  authToken: 'jt-token',
  name: 'User',
  email: 'user@example.com',
  machineID: 'machine-1',
}

function requestImage(overrides: Partial<RequestImageAttachment> = {}): RequestImageAttachment {
  return {
    variantId: 'sha256:variant-1' as never,
    attachment: {
      attachmentId: 'sha256:image-1' as never,
      mediaType: 'image/png',
      bytes: 3,
      width: 1,
      height: 1,
    },
    data: new Uint8Array([1, 2, 3]),
    mediaType: 'image/png',
    bytes: 3,
    width: 1,
    height: 1,
    depth: 'uchar',
    space: 'srgb',
    hasAlpha: true,
    ...overrides,
  } as RequestImageAttachment
}

const okUpload = (): Response => new Response(JSON.stringify({ result: { oss_url: 'https://oss.qoder.sh/a.png' } }))

test('publishes an image and returns the center object URL', async () => {
  let seen: { url: string; init?: RequestInit } | undefined
  const uploader = new QoderImageUploader({
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      seen = { url: String(input), init }
      return okUpload()
    }) as typeof fetch,
  })

  const url = await uploader.resolveImageUrl(requestImage(), credentials)
  assert.equal(url, 'https://oss.qoder.sh/a.png')
  assert.equal(seen?.init?.method, 'PUT')
  assert.match(seen?.url ?? '', /^https:\/\/center\.qoder\.sh\/algo\/api\/v2\/image\/upload\?request_id=/u)
})

test('signs the multipart body length rather than the raw bytes', async () => {
  let headers: Record<string, string> = {}
  let bodyLength = 0
  const uploader = new QoderImageUploader({
    fetch: (async (_input: RequestInfo | URL, init?: RequestInit) => {
      headers = init?.headers as Record<string, string>
      bodyLength = (init?.body as Uint8Array).byteLength
      return okUpload()
    }) as typeof fetch,
  })

  await uploader.resolveImageUrl(requestImage(), credentials)
  // The Qoder client passes String(body.length) to prepareRequest, so the
  // signed body hash must cover that decimal string, never the image bytes.
  const expected = createHashHex(String(bodyLength))
  assert.equal(headers['Cosy-Bodyhash'], expected)
  assert.equal(headers['Cosy-Bodylength'], String(String(bodyLength).length))
  assert.equal(headers['Cosy-Sigpath'], '/api/v2/image/upload')
  assert.match(headers['Content-Type'], /^multipart\/form-data; boundary=----qodercli-/u)
  assert.equal(headers['Content-Length'], String(bodyLength))
  assert.ok(headers['AI-CLIENT-TIMESTAMP'])
})

function createHashHex(value: string): string {
  return crypto.createHash('md5').update(Buffer.from(value, 'utf8')).digest('hex')
}

test('multipart payload carries one file field with the media-type extension', () => {
  const { body, boundary } = buildQoderImageMultipart(new Uint8Array([1, 2, 3]), 'image/jpeg', 'fixed')
  const text = body.toString('latin1')
  assert.equal(boundary, '----qodercli-fixed')
  assert.ok(text.startsWith('------qodercli-fixed\r\n'))
  assert.ok(text.includes('Content-Disposition: form-data; name="file"; filename="image.jpg"\r\n'))
  assert.ok(text.includes('Content-Type: image/jpeg\r\n\r\n'))
  assert.ok(text.endsWith('\r\n------qodercli-fixed--\r\n'))
  assert.ok(body.includes(Buffer.from([1, 2, 3])))
})

test('reads the documented response URL precedence and rejects unusable values', () => {
  assert.equal(readQoderImageUrl({ url: 'https://a/1' }), 'https://a/1')
  assert.equal(readQoderImageUrl({ result: { url: 'https://a/2' } }), 'https://a/2')
  assert.equal(readQoderImageUrl({ result: { oss_url: 'https://a/3' } }), 'https://a/3')
  assert.equal(readQoderImageUrl({ data: { url: 'https://a/4' } }), 'https://a/4')
  assert.equal(readQoderImageUrl({ data: { oss_url: 'https://a/5' } }), 'https://a/5')
  assert.equal(
    readQoderImageUrl({ url: 'https://first', result: { oss_url: 'https://second' } }),
    'https://first',
  )
  assert.equal(readQoderImageUrl({ url: '   ' }), undefined)
  assert.equal(readQoderImageUrl({ url: 'not a url' }), undefined)
  assert.equal(readQoderImageUrl(null), undefined)
})

test('remembers a published URL so an identical image uploads once', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    fetch: (async () => {
      uploads++
      return okUpload()
    }) as typeof fetch,
  })

  const first = await uploader.resolveImageUrl(requestImage(), credentials)
  const second = await uploader.resolveImageUrl(requestImage(), credentials)
  assert.equal(uploads, 1)
  assert.equal(first, second)
})

test('separates cached URLs by subscriber and by request variant', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    fetch: (async () => {
      uploads++
      return okUpload()
    }) as typeof fetch,
  })

  await uploader.resolveImageUrl(requestImage(), credentials)
  await uploader.resolveImageUrl(requestImage(), { ...credentials, userID: 'user-2' })
  await uploader.resolveImageUrl(requestImage({ variantId: 'sha256:variant-2' as never }), credentials)
  assert.equal(uploads, 3)
})

test('republishes an image after its remembered URL expires', async () => {
  let uploads = 0
  let clock = 1_000
  const uploader = new QoderImageUploader({
    cacheTtlMs: 60_000,
    now: () => clock,
    fetch: (async () => {
      uploads++
      return okUpload()
    }) as typeof fetch,
  })

  await uploader.resolveImageUrl(requestImage(), credentials)
  clock += 30_000
  await uploader.resolveImageUrl(requestImage(), credentials)
  assert.equal(uploads, 1)
  clock += 31_000
  await uploader.resolveImageUrl(requestImage(), credentials)
  assert.equal(uploads, 2)
})

test('evicts the coldest entry once the cache is full', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    cacheCapacity: 2,
    fetch: (async () => {
      uploads++
      return okUpload()
    }) as typeof fetch,
  })

  const a = requestImage({ variantId: 'v-a' as never })
  const b = requestImage({ variantId: 'v-b' as never })
  const c = requestImage({ variantId: 'v-c' as never })
  await uploader.resolveImageUrl(a, credentials)
  await uploader.resolveImageUrl(b, credentials)
  await uploader.resolveImageUrl(a, credentials) // refresh recency of a
  await uploader.resolveImageUrl(c, credentials) // evicts b
  assert.equal(uploads, 3)
  await uploader.resolveImageUrl(a, credentials)
  assert.equal(uploads, 3)
  await uploader.resolveImageUrl(b, credentials)
  assert.equal(uploads, 4)
})

test('shares one publication between concurrent callers', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    fetch: (async () => {
      uploads++
      await new Promise(resolve => setTimeout(resolve, 5))
      return okUpload()
    }) as typeof fetch,
  })

  const [first, second] = await Promise.all([
    uploader.resolveImageUrl(requestImage(), credentials),
    uploader.resolveImageUrl(requestImage(), credentials),
  ])
  assert.equal(uploads, 1)
  assert.equal(first, second)
})

test('keeps the request alive by degrading to a data URL', async () => {
  const cases: Array<{ name: string; respond: () => Response | Promise<Response> }> = [
    { name: 'server error', respond: () => new Response('', { status: 500 }) },
    { name: 'invalid json', respond: () => new Response('<html>') },
    { name: 'missing url', respond: () => new Response(JSON.stringify({ result: {} })) },
    { name: 'network failure', respond: () => { throw new Error('socket hang up') } },
  ]

  for (const scenario of cases) {
    const warnings: string[] = []
    const uploader = new QoderImageUploader({
      logger: { warn: (message: string) => warnings.push(message) },
      fetch: (async () => scenario.respond()) as typeof fetch,
    })
    const url = await uploader.resolveImageUrl(requestImage(), credentials)
    assert.equal(url, 'data:image/png;base64,AQID', scenario.name)
    assert.deepEqual(warnings, ['[image-upload] upload failed, keeping base64 image'], scenario.name)
  }
})

test('degrades when the upload exceeds its deadline', async () => {
  const warnings: string[] = []
  const uploader = new QoderImageUploader({
    timeoutMs: 10,
    logger: { warn: (message: string) => warnings.push(message) },
    fetch: ((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    })) as typeof fetch,
  })

  // AbortSignal.timeout does not hold the event loop open, and the stalled
  // fetch replacement has no socket to hold it either.
  const keepAlive = setTimeout(() => {}, 1_000)
  try {
    const url = await uploader.resolveImageUrl(requestImage(), credentials)
    assert.equal(url, 'data:image/png;base64,AQID')
    assert.equal(warnings.length, 1)
  } finally {
    clearTimeout(keepAlive)
  }
})

test('does not remember a degraded data URL', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    fetch: (async () => {
      uploads++
      return uploads === 1 ? new Response('', { status: 500 }) : okUpload()
    }) as typeof fetch,
  })

  assert.equal(await uploader.resolveImageUrl(requestImage(), credentials), 'data:image/png;base64,AQID')
  assert.equal(await uploader.resolveImageUrl(requestImage(), credentials), 'https://oss.qoder.sh/a.png')
  assert.equal(uploads, 2)
})

test('refreshes credentials once when the center rejects authorization', async () => {
  for (const status of [401, 403]) {
    let uploads = 0
    let refreshes = 0
    const uploader = new QoderImageUploader({
      refreshCredentials: async () => {
        refreshes++
        return { ...credentials, authToken: 'jt-refreshed' }
      },
      fetch: (async () => {
        uploads++
        return uploads === 1 ? new Response('', { status }) : okUpload()
      }) as typeof fetch,
    })

    const url = await uploader.resolveImageUrl(requestImage(), credentials)
    assert.equal(url, 'https://oss.qoder.sh/a.png')
    assert.equal(refreshes, 1)
    assert.equal(uploads, 2)
  }
})

test('degrades after a refreshed credential is still rejected', async () => {
  let uploads = 0
  const uploader = new QoderImageUploader({
    logger: { warn: () => {} },
    refreshCredentials: async () => credentials,
    fetch: (async () => {
      uploads++
      return new Response('', { status: 401 })
    }) as typeof fetch,
  })

  assert.equal(await uploader.resolveImageUrl(requestImage(), credentials), 'data:image/png;base64,AQID')
  assert.equal(uploads, 2)
})

test('propagates caller cancellation as an aborted error', async () => {
  const controller = new AbortController()
  const uploader = new QoderImageUploader({
    fetch: ((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    })) as typeof fetch,
  })

  const keepAlive = setTimeout(() => {}, 1_000)
  try {
    const pending = uploader.resolveImageUrl(requestImage(), credentials, controller.signal)
    controller.abort()
    await assert.rejects(pending, (error: Error) => {
      assert.ok(error instanceof QoderLlmError)
      assert.equal((error as QoderLlmError).code, 'ABORTED')
      return true
    })
  } finally {
    clearTimeout(keepAlive)
  }
})

test('bounds how many publications run at once', async () => {
  let active = 0
  let peak = 0
  const uploader = new QoderImageUploader({
    maxConcurrency: 2,
    fetch: (async () => {
      active++
      peak = Math.max(peak, active)
      await new Promise(resolve => setTimeout(resolve, 5))
      active--
      return okUpload()
    }) as typeof fetch,
  })

  await Promise.all(Array.from({ length: 6 }, (_value, index) =>
    uploader.resolveImageUrl(requestImage({ variantId: `v-${index}` as never }), credentials)))
  assert.equal(peak, 2)
})

test('targets center endpoints with /algo in the HTTP URL but not the signature path', () => {
  const url = getQoderImageUploadUrl('china', 'req-1')
  assert.equal(url, 'https://gateway.qoder.com.cn/algo/api/v2/image/upload?request_id=req-1')
  assert.equal(computeSigPath(url), '/api/v2/image/upload')
  assert.equal(
    getQoderImageUploadUrl('global', 'req-1'),
    'https://center.qoder.sh/algo/api/v2/image/upload?request_id=req-1',
  )
  assert.equal(computeSigPath(getQoderImageUploadUrl('global')), '/api/v2/image/upload')
})

test('cancelled queued uploads do not block later publications', async () => {
  const releases: Array<() => void> = []
  const uploader = new QoderImageUploader({
    maxConcurrency: 1,
    fetch: (async () => {
      await new Promise<void>(resolve => releases.push(resolve))
      return okUpload()
    }) as typeof fetch,
  })
  const cancelled = new AbortController()
  const remaining = new AbortController()
  const first = uploader.resolveImageUrl(requestImage(), credentials)
  const second = uploader.resolveImageUrl(requestImage({ variantId: 'cancelled' as never }), credentials, cancelled.signal)
  const third = uploader.resolveImageUrl(requestImage({ variantId: 'remaining' as never }), credentials, remaining.signal)
  const rejected = assert.rejects(second, { code: 'ABORTED' })
  cancelled.abort()
  await rejected
  releases.shift()!()
  await first
  await new Promise<void>(resolve => setImmediate(resolve))
  const started = releases.length
  if (started === 0) {
    const cleanup = assert.rejects(third, { code: 'ABORTED' })
    remaining.abort()
    await cleanup
  } else {
    releases.shift()!()
    await third
  }
  assert.equal(started, 1, 'the live queued upload must receive the released slot')
})
