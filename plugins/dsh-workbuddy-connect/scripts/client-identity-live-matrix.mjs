/**
 * Live matrix for the phase-1 chat identity (NOT part of the offline suite):
 * chat and probe requests present the desktop-form User-Agent while refresh,
 * catalog, and billing keep their long-standing headers. Runs the built
 * client against the real upstream with the machine's current credentials
 * read from the shared desktop-app auth directory (read-only; tokens are
 * never printed, accounts are anonymized in the output).
 *
 * Run from the package root:
 *
 *   node scripts/client-identity-live-matrix.mjs            # full matrix
 *   node scripts/client-identity-live-matrix.mjs intl-probe # one case
 *
 * Cases: cn-chat, cn-tool, intl-chat, intl-tool, cn-probe, intl-probe,
 * baseline-cn, baseline-intl. Results and the 2026-09-14 run are recorded
 * in docs/client-identity-live-verification-2026-09-14.md (local file).
 */

import { readFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { Readable } from 'node:stream'
import {
  WorkBuddyUpstreamClient,
  chatUserAgent,
  parseWorkBuddyAuth,
  prepareChatBody,
  resolveChatIdentity,
} from '../lib/index.js'

const AUTH_DIR = join(homedir(), 'Library/Application Support/CodeBuddyExtension/Data/Public/auth')
const CN = parseWorkBuddyAuth(await readFile(join(AUTH_DIR, 'workbuddy-desktop.info'), 'utf8'))
const INTL = parseWorkBuddyAuth(await readFile(join(AUTH_DIR, 'workbuddy-desktop-ai.info'), 'utf8'))
if (!CN || !INTL) throw new Error('credential files unreadable')

const client = new WorkBuddyUpstreamClient()
const cnIdentity = await resolveChatIdentity('cn')
const intlIdentity = await resolveChatIdentity('global')
const CN_UA = chatUserAgent(cnIdentity, 'cn')
const INTL_UA = chatUserAgent(intlIdentity, 'global')
const OLD_UA = 'CLI/2.63.2 CodeBuddy/2.63.2'
console.log(`CN  identity ${JSON.stringify(cnIdentity)} -> ${CN_UA}`)
console.log(`INT identity ${JSON.stringify(intlIdentity)} -> ${INTL_UA}`)

const TOOLS = [{
  type: 'function',
  function: { name: 'get_weather', parameters: { type: 'object', properties: { city: { type: 'string' } }, required: ['city'] } },
}]

/** Read an SSE response to its end, accumulating content and tool-call fragments. */
async function readSse(response) {
  const text = await Readable.fromWeb(response.body).reduce((acc, chunk) => acc + chunk.toString('utf8'), '')
  let finish, content = '', done = false, firstObject
  const calls = new Map()
  for (const event of text.split('\n\n')) {
    const dataLine = event.split('\n').find(l => l.startsWith('data:'))
    if (dataLine === undefined) continue
    const payload = dataLine.slice(5).trim()
    if (payload === '[DONE]') { done = true; continue }
    let parsed
    try { parsed = JSON.parse(payload) } catch { continue }
    if (firstObject === undefined && parsed.object !== undefined) firstObject = parsed.object
    if (parsed.choices?.[0]?.finish_reason) finish = parsed.choices[0].finish_reason
    const delta = parsed.choices?.[0]?.delta
    if (typeof delta?.content === 'string') content += delta.content
    for (const t of delta?.tool_calls ?? []) {
      const row = calls.get(t.index ?? 0) ?? { name: '', args: '' }
      if (t.function?.name) row.name += t.function.name
      if (t.function?.arguments) row.args += t.function.arguments
      calls.set(t.index ?? 0, row)
    }
  }
  return { http: response.status, finish, content, firstObject, done, calls: [...calls.values()] }
}

const chatBody = (model, messages, extra = {}) =>
  JSON.stringify({ model, stream: true, max_tokens: 1024, messages, ...extra })

/** Failed case ids; a non-empty list exits non-zero so re-runs are CI-usable. */
const failures = []

async function chat(id, credential, model, bodyJson, expect = 'answer', note = '') {
  const result = await client.chatStream(credential, bodyJson, AbortSignal.timeout(120_000))
  if (!result.ok) {
    failures.push(id)
    console.log(`FAIL #${id} http=${result.status} ${result.message.slice(0, 100)}`)
    return null
  }
  const facts = await readSse(result.response)
  const call = facts.calls.map(c => `${c.name}(${c.args})`).join('; ')
  // Strict per-case expectation: an answer leg must finish=stop WITH visible
  // content (a length-truncated thinking burn is a failure, not a pass); a
  // tool leg must finish=tool_calls WITH captured calls.
  const pass = expect === 'answer'
    ? facts.finish === 'stop' && facts.content.length > 0
    : facts.finish === 'tool_calls' && facts.calls.length > 0
  if (!pass) failures.push(id)
  console.log(`${pass ? 'PASS' : 'FAIL'} #${id} ${model} http=${facts.http} finish=${facts.finish} content=${facts.content.length}ch 「${facts.content.slice(0, 40)}」 tool=[${call}] done=${facts.done} firstObject=${facts.firstObject ?? '-'}${note ? ` ${note}` : ''}`)
  return pass ? facts : null
}

async function toolRound(prefix, credential, region, model, wrap) {
  const ask = [
    { role: 'system', content: 'Use the provided tool to answer.' },
    { role: 'user', content: 'What is the weather in Paris? You must call the tool.' },
  ]
  const first = await chat(`${prefix}-a`, credential, model, wrap(chatBody(model, ask, { tools: TOOLS, tool_choice: 'auto' })), 'toolcall')
  // The continuation leg is required: a missing tool_calls in the first leg,
  // or a failed/skipped second leg, fails the round.
  if (first === null) {
    failures.push(`${prefix}-b`)
    console.log(`FAIL #${prefix}-b (first leg produced no usable tool_calls; continuation cannot run)`)
    return
  }
  await chat(`${prefix}-b`, credential, model, wrap(chatBody(model, [
    ...ask,
    { role: 'assistant', content: '', tool_calls: [{ id: 'call_1', type: 'function', function: { name: first.calls[0].name, arguments: first.calls[0].args || '{}' } }] },
    { role: 'tool', tool_call_id: 'call_1', content: JSON.stringify({ temp_c: 21, condition: 'clear' }) },
  ])))
}

async function probe(id, credential, model, effort) {
  const attempt = await client.probeEffort(credential, model, effort, AbortSignal.timeout(30_000))
  const pass = attempt.status === 200 && attempt.streamed
  if (!pass) failures.push(id)
  console.log(`${pass ? 'PASS' : 'FAIL'} #${id} ${model} probe http=${attempt.status} streamed=${attempt.streamed} detail=${attempt.detail ?? ''}`)
}

/** The released v0.5.0 header set (old CLI UA) for before/after comparison. */
async function baseline(id, credential, region, model, bodyJson) {
  const origin = region === 'intl' ? 'https://www.workbuddy.ai' : 'https://www.codebuddy.cn'
  const headers = {
    'Accept': 'application/json, text/plain, */*',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': origin,
    'Referer': `${origin}/`,
    'User-Agent': OLD_UA,
    'Content-Type': 'application/json',
    ...(credential.uid === '' ? { 'X-No-User-Id': '1' } : { 'X-User-Id': credential.uid }),
    ...(credential.enterpriseId === undefined || credential.enterpriseId === ''
      ? { 'X-No-Enterprise-Id': '1' }
      : { 'X-Enterprise-Id': credential.enterpriseId }),
    ...(credential.domain === '' ? { 'X-No-Department-Info': '1' } : { 'X-Domain': credential.domain }),
    'X-Product': 'SaaS',
    'Authorization': `Bearer ${credential.accessToken}`,
  }
  const base = region === 'intl' ? 'https://www.workbuddy.ai' : 'https://copilot.tencent.com'
  const response = await fetch(`${base}/v2/chat/completions`, { method: 'POST', headers, body: bodyJson, signal: AbortSignal.timeout(120_000) })
  if (!response.ok) {
    failures.push(id)
    console.log(`FAIL #${id} baseline http=${response.status}`)
    return
  }
  const facts = await readSse(response)
  // Same strict rule as the answer legs: stop with visible content.
  const pass = facts.finish === 'stop' && facts.content.length > 0
  if (!pass) failures.push(id)
  console.log(`${pass ? 'PASS' : 'FAIL'} #${id} ${model} baseline(${OLD_UA}) http=${facts.http} finish=${facts.finish} content=${facts.content.length}ch`)
}

const wanted = process.argv.slice(2)
const run = name => wanted.length === 0 || wanted.includes(name)
const cnWrap = body => prepareChatBody(body)
const intlWrap = body => body

const balance = async c => { try { return (await client.fetchCredits(c)).total } catch { return 'n/a' } }
const cnBefore = await balance(CN)
const intlBefore = await balance(INTL)
console.log(`balance before: CN=${cnBefore} INTL=${intlBefore}`)

if (run('cn-chat')) await chat('cn-chat', CN, 'glm-5.3', cnWrap(chatBody('glm-5.3', [
  { role: 'system', content: 'Answer in one short sentence.' },
  { role: 'user', content: '用一句话说明什么是回环地址。' },
])))
if (run('cn-tool')) await toolRound('cn-tool', CN, 'cn', 'glm-5.3', cnWrap)
if (run('intl-chat')) await chat('intl-chat', INTL, 'gpt-5.6-luna', intlWrap(chatBody('gpt-5.6-luna', [
  { role: 'system', content: 'Answer in one short sentence.' },
  { role: 'user', content: 'Name the loopback address in one sentence.' },
])))
if (run('intl-tool')) await toolRound('intl-tool', INTL, 'intl', 'gpt-5.6-luna', intlWrap)
if (run('cn-probe')) await probe('cn-probe', CN, 'glm-5.2', 'low')
if (run('intl-probe')) await probe('intl-probe', INTL, 'gpt-5.3-codex', 'low')
if (run('baseline-cn')) await baseline('baseline-cn', CN, 'cn', 'glm-5.3', cnWrap(chatBody('glm-5.3', [
  { role: 'system', content: 'Answer in one short sentence.' },
  { role: 'user', content: '用一句话说明什么是回环地址。' },
])))
if (run('baseline-intl')) await baseline('baseline-intl', INTL, 'intl', 'gpt-5.6-luna', intlWrap(chatBody('gpt-5.6-luna', [
  { role: 'system', content: 'Answer in one short sentence.' },
  { role: 'user', content: 'Name the loopback address in one sentence.' },
])))

console.log(`balance after : CN=${await balance(CN)} INTL=${await balance(INTL)} (before CN=${cnBefore} INTL=${intlBefore})`)

if (failures.length > 0) {
  console.log(`\n=== FAILED: ${failures.join(', ')}`)
  process.exitCode = 1
} else {
  console.log('\n=== all requested cases passed')
}
