import test from 'node:test'
import assert from 'node:assert/strict'
import { QoderLlmError } from '../src/qoder/errors.ts'
import { parseQoderSse } from '../src/qoder/transport/wire/sse.ts'

function streamOf(lines: readonly string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const line of lines) controller.enqueue(encoder.encode(`${line}\n`))
      controller.close()
    },
  })
}

function data(body: unknown): string {
  return `data: ${JSON.stringify({ statusCodeValue: 200, body: JSON.stringify(body) })}`
}

const done = `data: ${JSON.stringify({ statusCodeValue: 200, body: '[DONE]' })}`

test('parseQoderSse unwraps text, disjoint usage, and envelope-body DONE', async () => {
  const body = JSON.stringify({
    choices: [{ delta: { content: 'Hello' }, finish_reason: 'stop' }],
    usage: {
      prompt_tokens: 12,
      completion_tokens: 2,
      prompt_tokens_details: { cached_tokens: 3, cache_write_tokens: 2 },
    },
  })
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    `data: ${JSON.stringify({ statusCodeValue: 200, body })}`,
    `data: ${JSON.stringify({ statusCodeValue: 200, body: '[DONE]' })}`,
  ]))) chunks.push(chunk)
  assert.deepEqual(chunks.map(chunk => chunk.type), ['block-start', 'text-delta', 'block-end', 'usage', 'finish'])
  assert.deepEqual((chunks[3] as { usage: unknown }).usage, {
    inputTokens: 7,
    outputTokens: 2,
    cacheReadTokens: 3,
    cacheWriteTokens: 2,
  })
})

test('parseQoderSse separates native reasoning and removes cross-channel thinking tags', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { reasoning_content: '<thinking>inspect the input' } }] }),
    data({ choices: [{ delta: { content: '</thinking>\n\nFinal answer' }, finish_reason: 'stop' }] }),
    done,
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.map(chunk => chunk.type), [
    'block-start', 'reasoning-delta', 'block-end',
    'block-start', 'text-delta', 'block-end', 'finish',
  ])
  assert.deepEqual((chunks[2] as { block: unknown }).block, { type: 'reasoning', text: 'inspect the input' })
  assert.deepEqual((chunks[5] as { block: unknown }).block, { type: 'text', text: 'Final answer' })
  assert.equal((chunks[6] as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse extracts thinking tags split across content chunks', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: '<thi' } }] }),
    data({ choices: [{ delta: { content: 'nk>careful</th' } }] }),
    data({ choices: [{ delta: { content: 'ink>\nanswer' }, finish_reason: 'stop' }] }),
    done,
  ]))) chunks.push(chunk)
  const blocks = chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block)
  assert.deepEqual(blocks, [
    { type: 'reasoning', text: 'careful' },
    { type: 'text', text: 'answer' },
  ])
})

test('parseQoderSse assembles interleaved parallel tool calls', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { tool_calls: [
      { index: 0, id: 'call-a', function: { name: 'add', arguments: '{"a":' } },
      { index: 1, id: 'call-b', function: { name: 'echo', arguments: '{"text":' } },
    ] } }] }),
    data({ choices: [{ delta: { tool_calls: [
      { index: 1, function: { arguments: '"ok"}' } },
      { index: 0, function: { arguments: '2}' } },
    ] }, finish_reason: 'tool_calls' }] }),
    done,
  ]))) chunks.push(chunk)

  const blocks = chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block)
  assert.deepEqual(blocks, [
    { type: 'tool-call', id: 'call-a', name: 'add', arguments: '{"a":2}' },
    { type: 'tool-call', id: 'call-b', name: 'echo', arguments: '{"text":"ok"}' },
  ])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'tool-calls')
})

test('parseQoderSse accepts the legacy function_call finish reason without a DONE sentinel', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: 'Reading the pull request first.' } }] }),
    data({ choices: [{ delta: { tool_calls: [
      { index: 0, id: 'call-legacy', function: { name: 'read_file' } },
    ] } }] }),
    data({ choices: [{ delta: { tool_calls: [
      { index: 0, function: { arguments: '{"path":"src/index.ts"}' } },
    ] } }] }),
    data({ choices: [{ delta: {}, finish_reason: 'function_call' }] }),
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block), [
    { type: 'text', text: 'Reading the pull request first.' },
    { type: 'tool-call', id: 'call-legacy', name: 'read_file', arguments: '{"path":"src/index.ts"}' },
  ])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'tool-calls')
})

test('parseQoderSse normalizes absent tool arguments to an empty object', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: 'call-empty', function: { name: 'ping' } }] } }] }),
    data({ choices: [{ delta: {}, finish_reason: 'tool_calls' }] }),
    done,
  ]))) chunks.push(chunk)
  const blockEnd = chunks.find(chunk => chunk.type === 'block-end')
  assert.deepEqual(blockEnd?.block, {
    type: 'tool-call', id: 'call-empty', name: 'ping', arguments: '{}',
  })
})

test('parseQoderSse tolerates subsequent tool-call deltas with empty string or null id', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: 'call-tolerant', function: { name: 'calc', arguments: '{"x":' } }] } }] }),
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: '', function: { arguments: '1' } }] } }] }),
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: null, function: { arguments: '0}' } }] } }] }),
    data({ choices: [{ delta: {}, finish_reason: 'tool_calls' }] }),
    done,
  ]))) chunks.push(chunk)
  const blockEnd = chunks.find(chunk => chunk.type === 'block-end')
  assert.deepEqual(blockEnd?.block, {
    type: 'tool-call', id: 'call-tolerant', name: 'calc', arguments: '{"x":10}',
  })
})

test('parseQoderSse tolerates subsequent tool-call deltas with empty string or null name', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: 'call-tolerant-name', function: { name: 'calc', arguments: '{"x":' } }] } }] }),
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: '', function: { name: '', arguments: '1' } }] } }] }),
    data({ choices: [{ delta: { tool_calls: [{ index: 0, id: null, function: { name: null, arguments: '0}' } }] } }] }),
    data({ choices: [{ delta: {}, finish_reason: 'tool_calls' }] }),
    done,
  ]))) chunks.push(chunk)
  const blockEnd = chunks.find(chunk => chunk.type === 'block-end')
  assert.deepEqual(blockEnd?.block, {
    type: 'tool-call', id: 'call-tolerant-name', name: 'calc', arguments: '{"x":10}',
  })
})

test('parseQoderSse accepts a reasoning-only response', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { reasoning_content: 'Only reasoning' }, finish_reason: 'stop' }] }),
    done,
  ]))) chunks.push(chunk)
  assert.deepEqual(chunks.map(chunk => chunk.type), [
    'block-start', 'reasoning-delta', 'block-end', 'finish',
  ])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse rejects malformed tool calls and unknown finish reasons', async () => {
  const invalidStreams = [
    [
      data({ choices: [{ delta: { tool_calls: [{ index: 0, id: 'call-bad', function: { name: 'bad', arguments: '{' } }] } }] }),
      done,
    ],
    [data({ choices: [{ delta: { content: 'blocked' }, finish_reason: 'new_reason' }] }), done],
  ]
  for (const lines of invalidStreams) {
    await assert.rejects(async () => {
      for await (const _chunk of parseQoderSse(streamOf(lines))) continue
    }, (error: Error) => error instanceof QoderLlmError && error.code === 'MALFORMED_RESPONSE')
  }
})

test('parseQoderSse accepts a final frame without a trailing newline', async () => {
  const encoder = new TextEncoder()
  const inner = JSON.stringify({ choices: [{ delta: { content: 'ok' } }] })
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ statusCodeValue: 200, body: inner })}\n`))
      controller.enqueue(encoder.encode('data: [DONE]'))
      controller.close()
    },
  })
  const chunks = []
  for await (const chunk of parseQoderSse(stream)) chunks.push(chunk)
  assert.equal(chunks.at(-1)?.type, 'finish')
})

test('parseQoderSse accepts statusless envelopes and ignores bodyless control frames', async () => {
  const inner = JSON.stringify({ choices: [{ delta: { content: 'ok' }, finish_reason: 'stop' }] })
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    `data: ${JSON.stringify({ event: 'ping' })}`,
    `data: ${JSON.stringify({ body: inner })}`,
    `data: ${JSON.stringify({ body: '[DONE]' })}`,
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.map(chunk => chunk.type), [
    'block-start', 'text-delta', 'block-end', 'finish',
  ])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse rejects invalid status, malformed body, and premature EOF', async () => {
  const invalid = [
    [`data: ${JSON.stringify({ statusCodeValue: '200', body: '{}' })}`],
    [`data: ${JSON.stringify({ statusCodeValue: 200, body: 42 })}`],
    [`data: ${JSON.stringify({ statusCodeValue: 200, body: '{}' })}`],
  ]
  for (const lines of invalid) {
    await assert.rejects(async () => {
      for await (const _chunk of parseQoderSse(streamOf(lines))) continue
    }, (error: Error) => {
      assert.ok(error instanceof QoderLlmError)
      return true
    })
  }
})

test('parseQoderSse completes a body closed without the DONE sentinel after a finish reason', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: 'complete-looking' }, finish_reason: 'stop' }] }),
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.map(chunk => chunk.type), ['block-start', 'text-delta', 'block-end', 'finish'])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse treats EOF before any finish reason as a retryable transport truncation', async () => {
  await assert.rejects(async () => {
    for await (const _chunk of parseQoderSse(streamOf([
      data({ choices: [{ delta: { content: 'half an ans' } }] }),
    ]))) continue
  }, (error: Error) => error instanceof QoderLlmError && error.code === 'TRANSPORT')
})

test('parseQoderSse ignores a null delta before DONE', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: 'Done.' } }] }),
    data({ choices: [{ delta: null, finish_reason: null }] }),
    done,
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block), [
    { type: 'text', text: 'Done.' },
  ])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse preserves completion across trailing null and empty tool deltas', async () => {
  for (const delta of [null, { tool_calls: [] }]) {
    const chunks = []
    for await (const chunk of parseQoderSse(streamOf([
      data({ choices: [{ delta: { content: 'Done.' }, finish_reason: 'stop' }] }),
      data({ choices: [{ delta, finish_reason: null }] }),
    ]))) chunks.push(chunk)

    assert.deepEqual(chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block), [
      { type: 'text', text: 'Done.' },
    ])
    assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
  }
})

test('parseQoderSse does not treat a control-only frame as stream completion', async () => {
  const truncated = [
    [data({ choices: [{ delta: null, finish_reason: null }] })],
    [data({ choices: [{ delta: { tool_calls: [] } }] })],
    [data({ choices: [{ delta: {}, finish_reason: null }] })],
    [data({ choices: [{ delta: {}, finish_reason: '' }] })],
    [data({ choices: [] })],
    [data({ usage: { prompt_tokens: 4, completion_tokens: 2 } })],
    [data({ choices: [{ delta: { role: 'assistant' } }] })],
  ]
  for (const lines of truncated) {
    await assert.rejects(async () => {
      for await (const _chunk of parseQoderSse(streamOf(lines))) continue
    }, (error: Error) => error instanceof QoderLlmError && error.code === 'TRANSPORT')
  }
})

test('parseQoderSse completes when the terminal reason arrives after the last streamed delta', async () => {
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: 'Done.' } }] }),
    data({ choices: [{ delta: {}, finish_reason: 'stop' }] }),
  ]))) chunks.push(chunk)

  assert.deepEqual(chunks.map(chunk => chunk.type), ['block-start', 'text-delta', 'block-end', 'finish'])
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'stop')
})

test('parseQoderSse requires the DONE sentinel once a terminal reason is followed by more content', async () => {
  const truncated = [
    data({ choices: [{ delta: { content: 'Answer so far.' }, finish_reason: 'stop' }] }),
    data({ choices: [{ delta: { content: ' and a tail that may be cut' } }] }),
  ]
  await assert.rejects(async () => {
    for await (const _chunk of parseQoderSse(streamOf(truncated))) continue
  }, (error: Error) => error instanceof QoderLlmError && error.code === 'TRANSPORT')

  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([...truncated, done]))) chunks.push(chunk)
  const blocks = chunks.filter(chunk => chunk.type === 'block-end').map(chunk => chunk.block)
  assert.deepEqual(blocks, [{ type: 'text', text: 'Answer so far. and a tail that may be cut' }])
})

test('parseQoderSse requires the DONE sentinel while another choice keeps streaming', async () => {
  await assert.rejects(async () => {
    for await (const _chunk of parseQoderSse(streamOf([
      data({ choices: [{ index: 0, delta: { content: 'first' }, finish_reason: 'stop' }] }),
      data({ choices: [{ index: 1, delta: { content: 'second' } }] }),
    ]))) continue
  }, (error: Error) => error instanceof QoderLlmError && error.code === 'TRANSPORT')
})

test('parseQoderSse relays an upstream tool-calls reason without inventing a tool-call block', async () => {
  // Deliberate, ADR-0009-documented limitation: the reported reason is relayed as received and no
  // tool-call block is synthesized for a turn that never streamed one.
  const chunks = []
  for await (const chunk of parseQoderSse(streamOf([
    data({ choices: [{ delta: { content: 'No tool after all.' }, finish_reason: 'function_call' }] }),
  ]))) chunks.push(chunk)

  assert.equal(chunks.some(chunk => chunk.type === 'block-end' && chunk.block.type === 'tool-call'), false)
  assert.equal((chunks.at(-1) as { reason: { kind: string } }).reason.kind, 'tool-calls')
})

test('parseQoderSse preserves explicit upstream error statuses', async () => {
  await assert.rejects(async () => {
    for await (const _chunk of parseQoderSse(streamOf([
      `data: ${JSON.stringify({ statusCodeValue: 503, body: 'unavailable' })}`,
    ]))) continue
  }, (error: Error) => (
    error instanceof QoderLlmError
    && error.code === 'SERVER'
    && error.failure.status === 503
    && error.message === 'Qoder service returned upstream error status 503.'
  ))
})

test('parseQoderSse rejects an oversized unterminated frame', async () => {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: 12345678901234567890'))
      controller.close()
    },
  })
  await assert.rejects(async () => {
    for await (const _chunk of parseQoderSse(stream, { maxBufferChars: 16 })) continue
  }, (error: Error) => error instanceof QoderLlmError && error.code === 'MALFORMED_RESPONSE')
})
