// dsh-knowledge-sqlite 冒烟测试（node 直驱 lib，验证 SQL 层真实工作）
import { SqliteKnowledgeStore } from './lib/store.js'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { tmpdir } from 'node:os'

const here = dirname(fileURLToPath(import.meta.url))
const exp = join(here, 'tests', 'fixtures', 'corpus')
const { memories, queries } = await import(pathToFileURL(join(exp, 'data.mjs')).href)
const enriched = JSON.parse(readFileSync(join(exp, 'enriched.json'), 'utf8'))
const allMemories = JSON.parse(readFileSync(join(exp, 'all-memories.json'), 'utf8'))
const distractors = JSON.parse(readFileSync(join(exp, 'distractors.json'), 'utf8'))
const expanded = JSON.parse(readFileSync(join(exp, 'expanded.json'), 'utf8'))
const humanQueries = JSON.parse(readFileSync(join(exp, 'human-queries.json'), 'utf8'))
const enrichById = new Map(enriched.map((e) => [e.id, e]))
const expandedById = new Map(expanded.map((e) => [e.id, e]))

const dbPath = join(tmpdir(), `knl-smoke-${Date.now()}.sqlite`)
const store = await SqliteKnowledgeStore.open(dbPath)
const stamps = { workspaceId: '/ws/verify', ownerId: 'owner-1', authorTier: 'explicit' }
const caller = { ...stamps, sessionId: 'owner-1' }
const actorId = 'owner-1'

// ---- seed ----
for (const m of allMemories) {
  const e = enrichById.get(m.id)
  const r = await store.write({ content: m.text, scope: 'workspace', dedupeKey: m.id, importance: e?.importance ?? 5 }, stamps, [], actorId)
  if ('error' in r) throw new Error(`write ${m.id}: ${r.error.message}`)
  if (e !== undefined) await store.enrich(r.id, { keywords: e.keywords ?? [], synonyms: e.synonyms ?? [], questions: e.questions ?? [] })
}
for (let i = 0; i < distractors.length; i++) {
  const r = await store.write({ content: String(distractors[i]).slice(0, 400), scope: 'workspace', dedupeKey: `d-${i}` }, { ...stamps, authorTier: 'llm' }, [], actorId)
  if ('error' in r) throw new Error(`distractor ${i}`)
}
console.log('seed OK, total =', store.dedupeIds().size)

// ---- 检索（确定性臂，应与 RESULTS-v3 一致：A 7% / C 21% / D 50%） ----
const dedupe = store.dedupeIds()
async function evalArm(table, textsOf) {
  let r1 = 0
  const ranks = []
  for (const q of queries) {
    const texts = textsOf(q)
    const rows = await store.search(table, texts, caller, { topN: 5 })
    const target = dedupe.get(q.target) ?? q.target
    const rank = rows.findIndex((r) => r.item.id === target)
    ranks.push(`${q.id}:${rank === -1 ? '-' : rank + 1}`)
    if (rank === 0) r1++
  }
  return `${r1}/14 (${Math.round((100 * r1) / 14)}%) [${ranks.join(' ')}]`
}
const hardA = await evalArm('base', (q) => [q.text])
const hardC = await evalArm('base', (q) => [q.text, ...(expandedById.get(q.id)?.variants ?? [])])
const hardD = await evalArm('rich', (q) => [q.text, ...(expandedById.get(q.id)?.variants ?? [])])
console.log('hard A:', hardA)
console.log('hard C:', hardC)
console.log('hard D:', hardD)
console.log('期望:  A 7%  C 21%  D 50%')

// human A
let r1 = 0
for (const q of humanQueries.filter((x) => x.target !== 'none')) {
  const rows = await store.search('base', [q.text], caller, { topN: 5 })
  const target = dedupe.get(q.target) ?? q.target
  if (rows.findIndex((r) => r.item.id === target) === 0) r1++
}
console.log(`human A: ${r1}/17 (${Math.round((100 * r1) / 17)}%) 期望 65%`)

// human C（离线 reasoner variants，0.1.4 诊断臂）
const humanExpanded = JSON.parse(readFileSync(join(exp, 'human-expanded.json'), 'utf8'))
const humanExpById = new Map(humanExpanded.map((e) => [e.id, e]))
let cR1 = 0
for (const q of humanQueries.filter((x) => x.target !== 'none')) {
  const vs = humanExpById.get(q.id)?.variants ?? []
  const rows = await store.search('base', [q.text, ...vs], caller, { topN: 5 })
  const target = dedupe.get(q.target) ?? q.target
  if (rows.findIndex((r) => r.item.id === target) === 0) cR1++
}
console.log(`human C: ${cR1}/17 (${Math.round((100 * cR1) / 17)}%) 期望 71%`)

// ---- 契约抽查 ----
// dedupeKey upsert id 稳定
const w1 = await store.write({ content: 'v1', dedupeKey: 'smoke-k' }, stamps, [], actorId)
const w2 = await store.write({ content: 'v2', dedupeKey: 'smoke-k' }, stamps, [], actorId)
console.log('dedupe upsert:', w1.id === w2.id ? 'id 稳定 ✓' : 'id 变化 ✗', w1.id)
// 打标伪造
const forged = await store.write({ content: 'x', workspaceId: 'ws-fake' }, stamps, [], actorId)
console.log('forged write:', 'error' in forged ? `拒绝 ✓ (${forged.error.code})` : '未拒绝 ✗')
// TTL
const ttl = await store.write({ content: 'TTL 冒烟', ttl: 1 }, stamps, [], actorId)
const ttlFresh = await store.search('rich', ['TTL 冒烟'], caller, { topN: 5 })
await new Promise((r) => setTimeout(r, 1100))
const ttlStale = await store.search('rich', ['TTL 冒烟'], caller, { topN: 5 })
console.log('TTL:', ttlFresh.some((r) => r.item.id === ttl.id) && !ttlStale.some((r) => r.item.id === ttl.id) ? '✓' : '✗')
// tombstone
const del = await store.write({ content: '冒烟删除', dedupeKey: 'smoke-del' }, stamps, [], actorId)
const before = await store.search('rich', ['冒烟删除'], caller, { topN: 5 })
const delR = await store.delete(del.id, caller)
const after = await store.search('rich', ['冒烟删除'], caller, { topN: 5 })
console.log('tombstone:', before.some((r) => r.item.id === del.id) && delR.deleted === true && !after.some((r) => r.item.id === del.id) ? '✓' : '✗')
// 跨 workspace
const alien = { workspaceId: '/ws/other', ownerId: 'alien', authorTier: 'explicit', sessionId: 'alien' }
const alienSearch = await store.search('rich', ['冒烟删除'], alien, { topN: 5 })
const alienDel = await store.delete(del.id, alien)
console.log('cross-ws:', alienSearch.length === 0 && 'error' in alienDel ? '✓' : '✗')
// list 分页
const pg1 = await store.list('all', { limit: 10 }, caller)
const pg2 = await store.list('all', { limit: 10, cursor: pg1.nextCursor }, caller)
console.log('pagination:', pg1.nextCursor !== undefined && pg2.items.length > 0 ? '✓' : '✗')

store.close()
console.log('db:', dbPath)
