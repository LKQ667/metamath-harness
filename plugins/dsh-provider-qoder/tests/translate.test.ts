import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ToolCallId,
  createAssistantMessage,
  createToolResultMessage,
  createUserMessage,
  ReasoningEffortId,
  type GenerateOptions,
  type Message,
} from '@deepseek-ai/dsh-llm'
import { QoderLlmError } from '../src/qoder/errors.ts'
import { normalizeQoderModels } from '../src/qoder/catalog.ts'
import { buildQoderRequestBody, validateQoderRequestShape } from '../src/qoder/transport/wire/serialize.ts'
import {
  validateAndTranslateMessages,
  type QoderImageAttachments,
  type QoderImageResolver,
} from '../src/qoder/transport/wire/translate.ts'

const imageRef = {
  attachmentId: 'sha256:image-1' as never,
  mediaType: 'image/png' as const,
  bytes: 3,
  width: 1,
  height: 1,
}

test('request preserves the discovered default tier and does not send ambiguous tier defaults', async () => {
  for (const conflicting of [false, true]) {
    const [model] = normalizeQoderModels({ assistant: [{
      key: 'model', enable: true, max_input_tokens: 180_000,
      context_config: {
        small: { token_count: 200_000, is_default: true },
        large: { token_count: 1_000_000, ...conflicting ? { is_default: true } : {} },
      },
      is_reasoning: true,
      thinking_config: { disabled: { is_default: true } },
    }] })
    const body = await buildQoderRequestBody({
      provider: 'dsh-provider-qoder', model: 'model',
      messages: [createUserMessage({ content: [{ type: 'text', text: 'Hello' }], source: { kind: 'user' } })],
    }, 'user-test', undefined, model)
    assert.equal(body.model_config.is_reasoning, false)
    assert.equal(body.chat_context.extra.modelConfig.is_reasoning, false)
    if (conflicting) {
      assert.equal(model.contextWindow, 180_000)
      assert.equal(body.model_config.context_config, undefined)
    } else {
      assert.equal(model.contextWindow, 200_000)
      assert.deepEqual(body.model_config.context_config, {
        small: { token_count: 200_000, is_default: true }, large: { token_count: 1_000_000 },
      })
    }
  }
})

function imageAttachments(onRead?: () => void): QoderImageAttachments {
  return {
    imageLimits: {
      maxImageBytes: 5 * 1024 * 1024,
      maxImagesPerMessage: 20,
      maxMessageImageBytes: 100 * 1024 * 1024,
      maxImagePixels: 40_000_000,
      maxImageDimension: 2_000,
      mediaTypes: ['image/png', 'image/jpeg', 'image/webp', 'image/gif'],
    },
    async readImageRequest(attachment) {
      onRead?.()
      return {
        variantId: 'sha256:variant-1' as never,
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
  }
}

test('validateAndTranslateMessages processes DSH text history', async () => {
  const messages = [
    createUserMessage({ content: [{ type: 'text', text: 'Hello' }], source: { kind: 'user' } }),
    createAssistantMessage({
      content: [{ type: 'text', text: 'Hi there!' }],
      source: {
        provider: 'dsh-provider-qoder',
        model: 'cmodel',
      },
    }),
  ]
  assert.deepEqual(await validateAndTranslateMessages(messages, 'System'), [
    { role: 'system', content: 'System' },
    { role: 'user', content: 'Hello' },
    { role: 'assistant', content: 'Hi there!' },
  ])
})

test('validateAndTranslateMessages preserves assistant reasoning across turns by default', async () => {
  const callId = ToolCallId('call-1')
  const assistant = createAssistantMessage({
    content: [
      { type: 'reasoning', text: 'The prior scratch work is retained.' },
      { type: 'text', text: 'I will add the values.' },
      { type: 'tool-call', id: callId, name: 'add', arguments: '{"a":2,"b":3}' },
    ],
    source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
  })
  const result = createToolResultMessage({
    callId,
    content: [{ type: 'text', text: '5' }, { type: 'text', text: ' total' }],
    isError: false,
  })
  assert.deepEqual(await validateAndTranslateMessages([assistant, result]), [
    {
      role: 'assistant',
      content: 'I will add the values.',
      tool_calls: [{
        id: 'call-1',
        type: 'function',
        function: { name: 'add', arguments: '{"a":2,"b":3}' },
      }],
      reasoning_content: 'The prior scratch work is retained.',
    },
    { role: 'tool', tool_call_id: 'call-1', content: '5 total' },
  ])
})

test('validateAndTranslateMessages preserves pure-reasoning assistant messages by default', async () => {
  const callId = ToolCallId('call-2')
  const toolOnly = createAssistantMessage({
    content: [{ type: 'tool-call', id: callId, name: 'ping', arguments: '{}' }],
    source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
  })
  const reasoningOnly = createAssistantMessage({
    content: [{ type: 'reasoning', text: 'deep thinking' }],
    source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
  })
  assert.deepEqual(await validateAndTranslateMessages([toolOnly, reasoningOnly]), [
    {
      role: 'assistant',
      content: ' ',
      tool_calls: [{ id: 'call-2', type: 'function', function: { name: 'ping', arguments: '{}' } }],
    },
    {
      role: 'assistant',
      content: ' ',
      reasoning_content: 'deep thinking',
    },
  ])
})

test('validateAndTranslateMessages drops reasoning when preserveThinking is false', async () => {
  const callId = ToolCallId('call-1')
  const assistant = createAssistantMessage({
    content: [
      { type: 'reasoning', text: 'The prior scratch work is not replayed.' },
      { type: 'text', text: 'I will add the values.' },
      { type: 'tool-call', id: callId, name: 'add', arguments: '{"a":2,"b":3}' },
    ],
    source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
  })
  const reasoningOnly = createAssistantMessage({
    content: [{ type: 'reasoning', text: 'transient' }],
    source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
  })
  const result = createToolResultMessage({
    callId,
    content: [{ type: 'text', text: '5' }],
    isError: false,
  })
  assert.deepEqual(await validateAndTranslateMessages([assistant, reasoningOnly, result], undefined, undefined, undefined, { preserveThinking: false }), [
    {
      role: 'assistant',
      content: 'I will add the values.',
      tool_calls: [{
        id: 'call-1',
        type: 'function',
        function: { name: 'add', arguments: '{"a":2,"b":3}' },
      }],
    },
    { role: 'tool', tool_call_id: 'call-1', content: '5' },
  ])
})

test('validateAndTranslateMessages tolerates reasoning blocks in user messages', async () => {
  const userMsg = createUserMessage({
    content: [
      { type: 'text', text: 'Context from previous agent:' },
      { type: 'reasoning', text: 'Injected reasoning block' },
      { type: 'text', text: 'Please proceed.' },
    ],
    source: { kind: 'user' },
  })
  assert.deepEqual(await validateAndTranslateMessages([userMsg]), [
    {
      role: 'user',
      content: 'Context from previous agent:Please proceed.',
    },
  ])
})

test('validateAndTranslateMessages inlines user images as ordered OpenAI data URLs', async () => {
  const message = createUserMessage({
    content: [
      { type: 'text', text: 'before' },
      { type: 'image', attachment: imageRef },
      { type: 'text', text: 'after' },
    ],
    source: { kind: 'user' },
  })

  assert.deepEqual(await validateAndTranslateMessages([message], undefined, imageAttachments()), [{
    role: 'user',
    content: [
      { type: 'text', text: 'before' },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,AQID' } },
      { type: 'text', text: 'after' },
    ],
  }])
})

test('validateAndTranslateMessages forwards tool-result images in a following user message', async () => {
  const result = createToolResultMessage({
    callId: ToolCallId('call-image'),
    content: [{ type: 'text', text: 'captured' }, { type: 'image', attachment: imageRef }],
    isError: false,
  })

  assert.deepEqual(await validateAndTranslateMessages([result], undefined, imageAttachments()), [
    { role: 'tool', tool_call_id: 'call-image', content: 'captured' },
    {
      role: 'user',
      content: [
        { type: 'text', text: '[1 image returned by the previous tool call]' },
        { type: 'image_url', image_url: { url: 'data:image/png;base64,AQID' } },
      ],
    },
  ])
})

test('validateAndTranslateMessages rejects assistant images and non-image tool-result content', async () => {
  const invalidMessages = [
    createAssistantMessage({
      content: [{ type: 'image' } as never],
      source: { provider: 'dsh-provider-qoder', model: 'cmodel' },
    }),
    createToolResultMessage({ callId: ToolCallId('call-invalid'), content: [{ type: 'reasoning', text: 'no' }], isError: false }),
  ]
  for (const message of invalidMessages) {
    await assert.rejects(() => validateAndTranslateMessages([message]), (error: Error) => {
      assert.ok(error instanceof QoderLlmError)
      assert.equal((error as QoderLlmError).code, 'UNSUPPORTED_CONTENT')
      return true
    })
  }
})

test('buildQoderRequestBody uses the resolved identity and configured model', async () => {
  const options = {
    provider: 'dsh-provider-qoder',
    model: 'custom-model',
    messages: [createUserMessage({ content: [{ type: 'text', text: 'Ping' }], source: { kind: 'user' } })],
    maxTokens: 4096,
    sessionId: 'session-1',
  } as GenerateOptions
  const body = await buildQoderRequestBody(options, 'user-42')
  assert.equal(body.session_type, 'qodercli')
  assert.equal(body.model_config.key, 'custom-model')
  assert.equal(body.parameters.max_tokens, 4096)
  assert.match(body.session_id, /^[a-f0-9]{16}-session-1$/)
})

test('buildQoderRequestBody applies discovered Qoder transport metadata', async () => {
  const options = {
    provider: 'dsh-provider-qoder',
    model: 'reasoner',
    messages: [createUserMessage({ content: [{ type: 'text', text: 'Think' }], source: { kind: 'user' } })],
    maxTokens: 32_000,
  } as GenerateOptions
  const body = await buildQoderRequestBody(options, 'user-42', undefined, {
    id: 'reasoner',
    name: 'Reasoner',
    maxTokens: 16_000,
    source: 'premium',
    isReasoning: true,
    contextOptions: { long: { tokenCount: 400_000, isDefault: true } },
  })
  assert.equal(body.parameters.max_tokens, 16_000)
  assert.equal(body.model_config.is_reasoning, true)
  assert.equal(body.model_config.source, 'premium')
  assert.deepEqual(body.model_config.context_config, {
    long: { token_count: 400_000, is_default: true },
  })
  assert.equal(body.chat_context.extra.modelConfig.is_reasoning, true)
})

test('buildQoderRequestBody sends DSH tool declarations', async () => {
  const messages: Message[] = [createUserMessage({ content: [{ type: 'text', text: 'Hi' }], source: { kind: 'user' } })]
  const body = await buildQoderRequestBody({
    provider: 'dsh-provider-qoder',
    model: 'cmodel',
    messages,
    tools: [{ name: 'tool', description: 'tool', parameters: {} }],
  }, 'user-42')
  assert.deepEqual(body.tools, [{
    type: 'function',
    function: { name: 'tool', description: 'tool', parameters: {} },
  }])
  assert.deepEqual(body.messages, [{ role: 'user', content: 'Hi' }])
})

test('buildQoderRequestBody preserves text metadata while inlining image content', async () => {
  const options = {
    provider: 'dsh-provider-qoder',
    model: 'vision',
    messages: [createUserMessage({
      content: [{ type: 'text', text: 'Inspect this' }, { type: 'image', attachment: imageRef }],
      source: { kind: 'user' },
    })],
  } as GenerateOptions
  const body = await buildQoderRequestBody(
    options,
    'user-42',
    undefined,
    { id: 'vision', name: 'Vision', supportsImages: true },
    imageAttachments(),
  )

  assert.deepEqual(body.messages, [{
    role: 'user',
    content: [
      { type: 'text', text: 'Inspect this' },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,AQID' } },
    ],
  }])
  assert.equal(body.chat_context.text, 'Inspect this')
  assert.equal(body.chat_context.extra.originalContent, 'Inspect this')
  assert.equal(body.image_urls, null)
  assert.equal(body.chat_context.imageUrls, null)
})

test('buildQoderRequestBody accepts only advertised reasoning efforts', async () => {
  const options = {
    provider: 'dsh-provider-qoder',
    model: 'reasoner',
    reasoningEffort: ReasoningEffortId('high'),
    messages: [createUserMessage({ content: [{ type: 'text', text: 'Think' }], source: { kind: 'user' } })],
  } as GenerateOptions
  const model = {
    id: 'reasoner',
    name: 'Reasoner',
    isReasoning: false,
    reasoningEfforts: [{ id: 'low', name: 'low' }, { id: 'high', name: 'high' }],
  }
  const body = await buildQoderRequestBody(options, 'user-42', undefined, model)
  assert.equal(body.parameters.reasoning_effort, 'high')
  assert.equal(body.model_config.is_reasoning, true)
  assert.equal(body.chat_context.extra.modelConfig.is_reasoning, true)

  options.reasoningEffort = ReasoningEffortId('off')
  await assert.rejects(
    () => buildQoderRequestBody(options, 'user-42', undefined, model),
    (error: Error) => error instanceof QoderLlmError && error.code === 'UNSUPPORTED_REASONING_EFFORT',
  )
})

function stubUploader(url = 'https://oss.qoder.sh/published.png'): {
  uploader: QoderImageResolver
  calls: number
} {
  const state = { calls: 0 }
  return {
    get calls() { return state.calls },
    uploader: {
      resolveImageUrl: async () => {
        state.calls++
        return url
      },
    },
  }
}

const stubCredentials = {
  userID: 'user-1',
  authToken: 'jt-token',
  name: 'User',
  email: 'user@example.com',
}

test('validateAndTranslateMessages carries published image URLs instead of base64', async () => {
  const stub = stubUploader()
  const message = createUserMessage({
    content: [
      { type: 'text', text: 'before' },
      { type: 'image', attachment: imageRef },
      { type: 'text', text: 'after' },
    ],
    source: { kind: 'user' },
  })

  assert.deepEqual(
    await validateAndTranslateMessages([message], undefined, imageAttachments(), undefined, {
      uploader: stub.uploader,
      credentials: stubCredentials,
    }),
    [{
      role: 'user',
      content: [
        { type: 'text', text: 'before' },
        { type: 'image_url', image_url: { url: 'https://oss.qoder.sh/published.png' } },
        { type: 'text', text: 'after' },
      ],
    }],
  )
  assert.equal(stub.calls, 1)
})

test('validateAndTranslateMessages preserves order across many published images', async () => {
  const message = createUserMessage({
    content: [
      { type: 'image', attachment: imageRef },
      { type: 'text', text: 'middle' },
      { type: 'image', attachment: imageRef },
      { type: 'image', attachment: imageRef },
    ],
    source: { kind: 'user' },
  })
  let index = 0
  const uploader: QoderImageResolver = {
    resolveImageUrl: async () => {
      const current = index++
      // Resolve out of order to prove slots are reserved, not appended.
      await new Promise(resolve => setTimeout(resolve, current === 0 ? 8 : 1))
      return `https://oss.qoder.sh/${current}.png`
    },
  }

  const [translated] = await validateAndTranslateMessages(
    [message], undefined, imageAttachments(), undefined, { uploader, credentials: stubCredentials },
  )
  assert.deepEqual(translated.content, [
    { type: 'image_url', image_url: { url: 'https://oss.qoder.sh/0.png' } },
    { type: 'text', text: 'middle' },
    { type: 'image_url', image_url: { url: 'https://oss.qoder.sh/1.png' } },
    { type: 'image_url', image_url: { url: 'https://oss.qoder.sh/2.png' } },
  ])
})

test('validateAndTranslateMessages publishes tool-result images in the following user message', async () => {
  const stub = stubUploader()
  const result = createToolResultMessage({
    callId: ToolCallId('call-image'),
    content: [{ type: 'text', text: 'captured' }, { type: 'image', attachment: imageRef }],
    isError: false,
  })

  assert.deepEqual(
    await validateAndTranslateMessages([result], undefined, imageAttachments(), undefined, {
      uploader: stub.uploader,
      credentials: stubCredentials,
    }),
    [
      { role: 'tool', tool_call_id: 'call-image', content: 'captured' },
      {
        role: 'user',
        content: [
          { type: 'text', text: '[1 image returned by the previous tool call]' },
          { type: 'image_url', image_url: { url: 'https://oss.qoder.sh/published.png' } },
        ],
      },
    ],
  )
  assert.equal(stub.calls, 1)
})

test('validateAndTranslateMessages rejects a batch that exceeds the image policy', async () => {
  const attachments = imageAttachments()
  const limited: QoderImageAttachments = {
    ...attachments,
    imageLimits: { ...attachments.imageLimits, maxImagesPerMessage: 2 },
  }
  const message = createUserMessage({
    content: [
      { type: 'image', attachment: imageRef },
      { type: 'image', attachment: imageRef },
      { type: 'image', attachment: imageRef },
    ],
    source: { kind: 'user' },
  })

  await assert.rejects(
    () => validateAndTranslateMessages([message], undefined, limited),
    (error: Error) => {
      assert.equal((error as QoderLlmError).code, 'UNSUPPORTED_CONTENT')
      return true
    },
  )
})

test('validateQoderRequestShape rejects images for a non-vision model with no I/O', () => {
  let reads = 0
  const options = {
    provider: 'dsh-provider-qoder',
    model: 'text-only',
    messages: [createUserMessage({
      content: [{ type: 'image', attachment: imageRef }],
      source: { kind: 'user' },
    })],
  } as GenerateOptions

  assert.throws(
    () => validateQoderRequestShape(options, { id: 'text-only', name: 'Text', supportsImages: false }),
    (error: Error) => {
      assert.ok(error instanceof QoderLlmError)
      assert.equal((error as QoderLlmError).code, 'UNSUPPORTED_CONTENT')
      return true
    },
  )
  assert.equal(reads, 0)
})
