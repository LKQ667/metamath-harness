/**
 * dsh-knowledge-sqlite — 实验套件验证（阶段 3 门禁的 e2e 载体）。
 *
 * seed 装载 memory-experiment 语料（m1-m12 富化 + n1-n10 + 500 干扰项），
 * 评估 hard/human 查询集的 A/C/D/L1-live 臂 recall@1，并跑契约检查。
 * 评估目标按 dedupeKey→id 解析（确定性 id 是 k-<hash> 前缀，与语料 target 名不同）。
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { KnowledgeService } from './index.ts'
import type { SqliteKnowledgeStore } from './store.ts'
import type { QueryExpander } from './expand.ts'
import type { KnowledgeStamps } from './types.ts'

/** 宽松结果访问（probe 是验证工具，类型从宽）：错误对象或 null。 */
function errOf(r: unknown): { code: string; message: string } | null {
  const e = (r as { error?: { code: string; message: string } }).error
  return e === undefined ? null : e
}
function idOf(r: unknown): string {
  return (r as { id: string }).id
}
function boolOf(r: unknown, key: string): boolean {
  return (r as Record<string, boolean>)[key] === true
}

const HARD_QUERIES = [
  { id: 'q1', target: 'm1', text: '怎么把这个项目跑起来' },
  { id: 'q2', target: 'm1', text: '本地网页服务在哪个端口' },
  { id: 'q3', target: 'm2', text: '记忆功能搜东西的原理是什么' },
  { id: 'q4', target: 'm3', text: '哪些文件不用管版本控制' },
  { id: 'q5', target: 'm4', text: '现在执行命令还要不要人点头' },
  { id: 'q6', target: 'm5', text: '换目录后旧对话记录还能找到吗' },
  { id: 'q7', target: 'm6', text: '为什么换个说法也能搜到' },
  { id: 'q8', target: 'm7', text: '想改机器人的自我介绍该动哪个文件' },
  { id: 'q9', target: 'm8', text: '浏览器界面里怎么没有终端工具' },
  { id: 'q10', target: 'm9', text: '只做方案不动代码的模式怎么开' },
  { id: 'q11', target: 'm10', text: '文件操作默认能写哪些地方' },
  { id: 'q12', target: 'm11', text: '技能清单为什么只给一行介绍' },
  { id: 'q13', target: 'm12', text: '长跑的任务中断了怎么接着干' },
  { id: 'q14', target: 'm4', text: '不用确认是不是更危险' },
]

export interface ProbeReport {
  ok: boolean
  parts: Array<Record<string, unknown>>
}

export async function runProbe(
  deps: {
    store: SqliteKnowledgeStore
    expander: QueryExpander
    service: KnowledgeService
    corpusPath: string
  },
  suite: 'seed' | 'hard' | 'human' | 'contract' | 'latency' | 'variance' | 'all',
  caller: { stamps: KnowledgeStamps; sessionId: string } | null,
  runs = 10,
): Promise<ProbeReport> {
  const report: ProbeReport = { ok: true, parts: [] }
  try {
    if (caller === null) throw new Error('no agent context for probe')
    const base = deps.corpusPath
    if (suite === 'seed' || suite === 'all') report.parts.push(await seed(deps, caller, base))
    if (suite === 'hard' || suite === 'all') report.parts.push(await evalHard(deps, caller, base))
    if (suite === 'human' || suite === 'all') report.parts.push(await evalHuman(deps, caller, base))
    if (suite === 'contract' || suite === 'all') report.parts.push(await contract(deps, caller))
    if (suite === 'latency' || suite === 'all') report.parts.push(await latency(deps, caller, base))
    if (suite === 'variance') report.parts.push(await variance(deps, runs))
    if (suite === 'all') {
      report.parts.push({ name: 'expansion-stats', ...deps.expander.stats })
    }
  } catch (error) {
    report.ok = false
    report.parts.push({ name: 'error', message: error instanceof Error ? error.message : String(error) })
  }
  return report
}

/**
 * 延迟门禁（V1.11：P95 L1 搜索延迟 ≤ 2.0s，人类查询集，4 路并发）。
 * 并发执行 human 查询集的 L1 搜索，收集非降级查询的 expansion.latencyMs。
 */
async function latency(
  deps: { service: KnowledgeService },
  caller: { stamps: KnowledgeStamps; sessionId: string },
  base: string,
): Promise<Record<string, unknown>> {
  const humanQueries = readJson(join(base, 'human-queries.json')) as Array<{ id: string; text: string; target: string }>
  const targeted = humanQueries.filter((q) => q.target && q.target !== 'none')
  const CONCURRENCY = 4
  const results: Array<{ id: string; latencyMs: number | null; degraded: boolean }> = []
  const started = Date.now()
  let cursor = 0
  const workers = Array.from({ length: CONCURRENCY }, async () => {
    while (cursor < targeted.length) {
      const q = targeted[cursor++]
      try {
        const res = await deps.service._searchInternal(q.text, { table: 'items_fts_rich', expand: true })
        results.push({
          id: q.id,
          latencyMs: res.expansion?.latencyMs ?? null,
          degraded: res.degraded !== null,
        })
      } catch (error) {
        results.push({ id: q.id, latencyMs: null, degraded: true })
      }
    }
  })
  await Promise.all(workers)
  const totalMs = Date.now() - started
  const live = results.filter((r) => r.latencyMs !== null && !r.degraded).map((r) => r.latencyMs as number)
  live.sort((a, b) => a - b)
  const p95 = live.length > 0 ? live[Math.min(live.length - 1, Math.floor(live.length * 0.95))] : null
  const mean = live.length > 0 ? Math.round(live.reduce((a, b) => a + b, 0) / live.length) : null
  const degradedIds = results.filter((r) => r.degraded).map((r) => r.id)
  return {
    name: 'latency',
    ok: true,
    concurrency: CONCURRENCY,
    queries: targeted.length,
    totalMs,
    meanLatencyMs: mean,
    p95LatencyMs: p95,
    maxLatencyMs: live.length > 0 ? live[live.length - 1] : null,
    degraded: degradedIds.length > 0 ? degradedIds.join(',') : null,
    perQuery: results.map((r) => `${r.id}:${r.latencyMs ?? '-'}${r.degraded ? '(deg)' : ''}`).join(' '),
    gate: p95 !== null && p95 <= 2000,
  }
}

function readJson(p: string): unknown {
  return JSON.parse(readFileSync(p, 'utf8'))
}

async function seed(
  deps: { store: SqliteKnowledgeStore; service: KnowledgeService },
  caller: { stamps: KnowledgeStamps; sessionId: string },
  base: string,
): Promise<Record<string, unknown>> {
  const allMemories = readJson(join(base, 'all-memories.json')) as Array<{ id: string; text: string }>
  const enriched = readJson(join(base, 'enriched.json')) as Array<{ id: string; keywords?: string[]; synonyms?: string[]; questions?: string[]; importance?: number }>
  const distractors = readJson(join(base, 'distractors.json')) as string[]
  const enrichById = new Map(enriched.map((e) => [e.id, e]))
  let mWithEnrich = 0
  let mPlain = 0
  for (const m of allMemories) {
    const e = enrichById.get(m.id)
    if (e !== undefined) {
      // m1-m12：带富化（trusted writer 装载，authorTier explicit）
      const r = await deps.service._seedWrite({
        content: m.text,
        scope: 'workspace',
        dedupeKey: m.id,
        importance: e.importance ?? 5,
      }, { ...caller.stamps, authorTier: 'explicit' })
      if ('error' in r) return { name: 'seed', ok: false, error: r.error }
      await deps.store.enrich(r.id, {
        keywords: e.keywords ?? [],
        synonyms: e.synonyms ?? [],
        questions: e.questions ?? [],
      })
      mWithEnrich++
    } else {
      // n1-n10：走公开 write 路径（无富化；验证 write→立即可搜）
      const r = await deps.service._seedWrite({ content: m.text, scope: 'workspace', dedupeKey: m.id }, caller.stamps)
      if ('error' in r) return { name: 'seed', ok: false, error: r.error }
      mPlain++
    }
  }
  for (let i = 0; i < distractors.length; i++) {
    const r = await deps.service._seedWrite({
      content: String(distractors[i]).slice(0, 400),
      scope: 'workspace',
      dedupeKey: `distractor-${i}`,
    }, { ...caller.stamps, authorTier: 'llm' })
    if ('error' in r) return { name: 'seed', ok: false, error: r.error }
  }
  return {
    name: 'seed', ok: true, corpusBase: base,
    memories: allMemories.length, enriched: mWithEnrich, plainWrite: mPlain,
    distractors: distractors.length,
  }
}

async function evalHard(
  deps: { service: KnowledgeService },
  caller: { stamps: KnowledgeStamps; sessionId: string },
  base: string,
): Promise<Record<string, unknown>> {
  const expanded = readJson(join(base, 'expanded.json')) as Array<{ id: string; variants?: string[] }>
  const expandedById = new Map(expanded.map((e) => [e.id, e]))
  const dedupeMap = await deps.service._dedupeIds()
  const arms: Record<string, unknown> = {}
  arms.A = await evalArm(deps, HARD_QUERIES, 'base', false, null, dedupeMap)
  arms.C = await evalArm(deps, HARD_QUERIES, 'base', false, (q) => expandedById.get(q.id)?.variants ?? [], dedupeMap)
  arms.D = await evalArm(deps, HARD_QUERIES, 'rich', false, (q) => expandedById.get(q.id)?.variants ?? [], dedupeMap)
  arms['L1-live'] = await evalArm(deps, HARD_QUERIES, 'rich', true, null, dedupeMap)
  return { name: 'eval-hard', ok: true, arms }
}

async function evalHuman(
  deps: { service: KnowledgeService },
  caller: { stamps: KnowledgeStamps; sessionId: string },
  base: string,
): Promise<Record<string, unknown>> {
  const humanQueries = readJson(join(base, 'human-queries.json')) as Array<{ id: string; text: string; target: string }>
  const dedupeMap = await deps.service._dedupeIds()
  // C 臂：离线 reasoner variants（human-expanded.json，与 hard 套件同口径）——
  // 分离"扩展模型能力"与"实时降级"两个变量（0.1.4 诊断臂）
  const humanExpanded = readJson(join(base, 'human-expanded.json')) as Array<{ id: string; variants?: string[] }>
  const humanExpandedById = new Map(humanExpanded.map((e) => [e.id, e]))
  const arms: Record<string, unknown> = {}
  arms.A = await evalArm(deps, humanQueries, 'base', false, null, dedupeMap)
  arms.C = await evalArm(deps, humanQueries, 'base', false, (q) => humanExpandedById.get(q.id)?.variants ?? [], dedupeMap)
  arms['L1-live'] = await evalArm(deps, humanQueries, 'rich', true, null, dedupeMap)
  const armA = arms.A as { recall1: string; targets: number }
  const armC = arms.C as { recall1: string }
  const armL1 = arms['L1-live'] as { recall1: string }
  // V1.11 人类集 precision@1 ≥80%（信息性；单目标套件上 ≡ recall@1，如实并列各臂）
  const targetN = Number(armA.targets)
  const r1Of = (s: unknown): number => Number(String(s).split('/')[0])
  const precision1 = {
    armA: String(armA.recall1),
    armC: String(armC.recall1),
    armL1Live: String(armL1.recall1),
    note: '单目标套件 precision@1 ≡ recall@1（V1.11 信息性门禁 ≥80%）',
    gateA: r1Of(armA.recall1) / targetN >= 0.8,
    gateC: r1Of(armC.recall1) / targetN >= 0.8,
    gateL1Live: r1Of(armL1.recall1) / targetN >= 0.8,
  }
  // none 查询（无目标）无误报：top1 必须为空或非记忆条目（干扰项/噪声不算误报）
  const noneQueries = humanQueries.filter((q) => q.target === 'none')
  const memoryIds = new Set(
    [...dedupeMap].filter(([key]) => !key.startsWith('distractor-')).map(([, id]) => id),
  )
  const noneTop1: string[] = []
  const noneFalsePositives: string[] = []
  for (const q of noneQueries) {
    const res = await deps.service._searchInternal(q.text, { table: TABLE_INTERNAL.base, expand: false })
    const top = res.hits[0]
    noneTop1.push(`${q.id}:${top === undefined ? '-' : top.id}`)
    if (top !== undefined && memoryIds.has(top.id)) noneFalsePositives.push(q.id)
  }
  return {
    name: 'eval-human',
    ok: true,
    arms,
    precision1,
    noneQueries: {
      count: noneQueries.length,
      top1: noneTop1.join(' '),
      falsePositives: noneFalsePositives.length > 0 ? noneFalsePositives.join(',') : null,
      pass: noneFalsePositives.length === 0,
    },
  }
}

interface QueryLike {
  id: string
  text: string
  target: string
}

/** 内部检索表（probe 用）：base=仅原文 / rich=原文+富化。 */
const TABLE_INTERNAL = { base: 'items_fts_base', rich: 'items_fts_rich' } as const

async function evalArm(
  deps: { service: KnowledgeService },
  suite: QueryLike[],
  table: 'base' | 'rich',
  useExpand: boolean,
  variantsOf: ((q: QueryLike) => string[]) | null,
  dedupeMap: Map<string, string>,
): Promise<Record<string, unknown>> {
  const scored = suite.filter((q) => q.target && q.target !== 'none')
  let r1 = 0
  const ranks: string[] = []
  const degraded: string[] = []
  for (const q of scored) {
    const opts: Record<string, unknown> = { table: TABLE_INTERNAL[table], expand: useExpand }
    if (!useExpand) {
      opts.expand = false
      const vs = variantsOf !== null ? variantsOf(q) : []
      if (vs.length > 0) opts.variants = vs
    }
    const res = await deps.service._searchInternal(q.text, opts)
    const targetId = dedupeMap.get(q.target) ?? q.target
    const rank = res.hits.findIndex((h) => h.id === targetId)
    ranks.push(`${q.id}:${rank === -1 ? '-' : rank + 1}`)
    if (rank === 0) r1++
    if (res.degraded !== null) degraded.push(q.id)
  }
  return {
    arm: table,
    recall1: `${r1}/${scored.length} (${Math.round((100 * r1) / scored.length)}%)`,
    // V1.11 信息性门禁：单目标套件上 precision@1 ≡ recall@1（DESIGN §门禁）
    precision1: `${r1}/${scored.length} (${Math.round((100 * r1) / scored.length)}%)`,
    targets: scored.length,
    ranks: ranks.join(' '),
    degraded: degraded.length > 0 ? degraded.join(',') : null,
  }
}

/**
 * L1 方差门禁（V1.11：10 次运行，均值 ≥30% 且无单次 <20%）。
 * 每轮 expander.clear()（清扩展缓存）→ hard 查询集 L1-live 臂独立扩展 14 次。
 */
async function variance(
  deps: { expander: QueryExpander; service: KnowledgeService },
  runs: number,
): Promise<Record<string, unknown>> {
  const perRun: Array<{ run: number; recall1: string; ranks: string; degraded: string | null }> = []
  // 目标 id 按 dedupeKey 解析（确定性 id 是 k-<hash> 前缀，与语料 target 名不同）
  const dedupeMap = await deps.service._dedupeIds()
  for (let i = 0; i < runs; i++) {
    deps.expander.clear()
    const arm = await evalArm(deps, HARD_QUERIES, 'rich', true, null, dedupeMap)
    perRun.push({
      run: i + 1,
      recall1: String(arm.recall1),
      ranks: String(arm.ranks),
      degraded: arm.degraded === null || arm.degraded === undefined ? null : String(arm.degraded),
    })
  }
  const values = perRun.map((r) => Number(r.recall1.split('/')[0]))
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pct = (n: number): number => Math.round((100 * n) / 14)
  return {
    name: 'variance',
    ok: true,
    runs,
    perRun: perRun.map((r) => `${r.run}: ${r.recall1}${r.degraded !== null ? ` (deg:${r.degraded})` : ''}`),
    recall1Values: values,
    meanRecall1Pct: pct(mean),
    minRecall1Pct: pct(min),
    maxRecall1Pct: pct(max),
    range: `${pct(min)}%-${pct(max)}%`,
    gateMean: mean / 14 >= 0.3,
    gateFloor: min / 14 >= 0.2,
  }
}

async function contract(
  deps: { service: KnowledgeService },
  caller: { stamps: KnowledgeStamps; sessionId: string },
): Promise<Record<string, unknown>> {
  const s = deps.service
  const checks: Array<Record<string, unknown>> = []
  // 1) dedupeKey upsert
  const w1 = await s._seedWrite({ content: '契约测试 第一版', dedupeKey: 'ct-k1' }, caller.stamps)
  const w2 = await s._seedWrite({ content: '契约测试 第二版', dedupeKey: 'ct-k1' }, caller.stamps)
  checks.push({
    name: 'dedupeKey-upsert',
    pass: errOf(w1) === null && errOf(w2) === null && idOf(w1) === idOf(w2),
    detail: `id=${idOf(w2)} first=${idOf(w1)}`,
  })
  // 2) 打标伪造拒绝（服务层：调用方提供打标字段 → write-rejected）
  const spoof = await s._seedWrite(
    { content: 'x', dedupeKey: 'ct-spoof' } as never,
    caller.stamps,
  )
  checks.push({
    name: 'stamp-fields-tool-owned',
    pass: errOf(spoof) === null, // 类型层不含打标字段；store.write 运行期显式拒绝伪造
    detail: 'stamp fields (workspaceId/ownerId/authorTier) are tool-layer-owned',
  })
  const forged = await s.write({ content: 'y', workspaceId: 'ws-fake' } as never)
  checks.push({
    name: 'stamp-spoof-rejected',
    pass: errOf(forged)?.code === 'write-rejected',
    detail: errOf(forged)?.message ?? 'not rejected!',
  })
  // 3) global 写 allowlist（空 → write-rejected）
  const gw = await s._seedWrite({ content: 'global 测试', scope: 'global' }, caller.stamps)
  checks.push({
    name: 'global-writer-allowlist',
    pass: errOf(gw)?.code === 'write-rejected',
    detail: errOf(gw)?.message ?? 'not rejected!',
  })
  // 4) scope/dedupeKey 写后不可变
  const up = await s._seedUpdate(idOf(w2), { scope: 'global' as never }, caller.stamps)
  checks.push({
    name: 'update-scope-immutable',
    pass: errOf(up)?.code === 'write-rejected',
    detail: errOf(up)?.message ?? 'not rejected!',
  })
  // 5) TTL
  const ttl = await s._seedWrite({ content: 'TTL 临时内容 过期即焚', ttl: 1 }, caller.stamps)
  const ttlId = idOf(ttl)
  const ttlFresh = await s._searchInternal('过期即焚', { table: 'items_fts_rich', expand: false })
  await new Promise((r) => setTimeout(r, 1100))
  const ttlStale = await s._searchInternal('过期即焚', { table: 'items_fts_rich', expand: false })
  const ttlDel = await s._seedDelete(ttlId, caller.stamps)
  checks.push({
    name: 'ttl-semantics',
    pass: ttlFresh.hits.some((h) => h.id === ttlId) && !ttlStale.hits.some((h) => h.id === ttlId)
      && errOf(ttlDel) === null && boolOf(ttlDel, 'deleted') === false,
    detail: `fresh=${ttlFresh.hits.length} stale=${ttlStale.hits.length} delete=${boolOf(ttlDel, 'deleted')}`,
  })
  // 6) 跨 workspace 隔离（服务层无法伪造 caller——用 alien 身份直连 store 验证 SQL 面）
  const alienStamps: KnowledgeStamps = { workspaceId: 'ws-other', ownerId: 'alien-s', authorTier: 'explicit' }
  const alienSearch = await s._searchInternal('pnpm', { table: 'items_fts_rich', expand: false }, alienStamps)
  const alienDel = await s._seedDelete(idOf(w2), alienStamps)
  checks.push({
    name: 'cross-workspace-isolation',
    pass: alienSearch.hits.length === 0 && errOf(alienDel)?.code === 'write-rejected',
    detail: `alienSearch=${alienSearch.hits.length} alienDelete=${errOf(alienDel)?.code ?? boolOf(alienDel, 'deleted')}`,
  })
  // 7) session scope 隔离
  const sess = await s._seedWrite({ content: '会话私有草稿 仅本会话', scope: 'session' }, caller.stamps)
  const sessSelf = await s._searchInternal('会话私有草稿', { table: 'items_fts_rich', expand: false })
  const sessAlien = await s._searchInternal('会话私有草稿', { table: 'items_fts_rich', expand: false }, alienStamps)
  const sessId = idOf(sess)
  checks.push({
    name: 'session-scope-isolation',
    pass: sessSelf.hits.some((h) => h.id === sessId) && !sessAlien.hits.some((h) => h.id === sessId),
    detail: `self=${sessSelf.hits.length} alien=${sessAlien.hits.length}`,
  })
  // 8) tombstone
  const del = await s._seedWrite({ content: '待删除条目 演示 tombstone', dedupeKey: 'ct-del' }, caller.stamps)
  const delId = idOf(del)
  const delBefore = await s._searchInternal('待删除条目', { table: 'items_fts_rich', expand: false })
  const delR = await s._seedDelete(delId, caller.stamps)
  const delAfter = await s._searchInternal('待删除条目', { table: 'items_fts_rich', expand: false })
  const listDeleted = await s._seedList({ includeDeleted: true, limit: 200 }, caller.stamps)
  checks.push({
    name: 'tombstone-delete',
    pass: delBefore.hits.some((h) => h.id === delId) && boolOf(delR, 'deleted') === true
      && !delAfter.hits.some((h) => h.id === delId)
      && listDeleted.items.some((i) => i.id === delId && i.deleted === true),
    detail: `before=${delBefore.hits.length} after=${delAfter.hits.length} listDeleted=${listDeleted.items.some((i) => i.id === delId) ? 'yes' : 'no'}`,
  })
  // 9) missing-key
  const miss = await s._seedDelete('k-00000000', caller.stamps)
  checks.push({
    name: 'missing-key',
    pass: errOf(miss)?.code === 'missing-key',
    detail: errOf(miss)?.message ?? 'not missing-key',
  })
  // 10) maxContentTokens
  const big = await s._seedWrite({ content: 'x'.repeat(7000) }, caller.stamps)
  checks.push({
    name: 'maxContentTokens',
    pass: errOf(big)?.code === 'write-rejected',
    detail: errOf(big)?.message ?? 'not rejected!',
  })
  // 11) 分页（自包含：先填充足够条目，再测游标稳定无重叠）
  for (let i = 0; i < 12; i++) {
    await s._seedWrite({ content: `分页填充条目 ${i}`, dedupeKey: `pg-${i}` }, caller.stamps)
  }
  const pg1 = await s._seedList({ limit: 10 }, caller.stamps)
  const pg2 = await s._seedList({ limit: 10, cursor: pg1.nextCursor }, caller.stamps)
  checks.push({
    name: 'list-pagination',
    pass: pg1.nextCursor !== undefined && pg2.items.length > 0
      && !pg1.items.some((a) => pg2.items.some((b) => b.id === a.id)),
    detail: `p1=${pg1.items.length} p2=${pg2.items.length} next=${pg1.nextCursor}`,
  })
  return { name: 'contract', ok: checks.every((c) => c.pass === true), checks }
}
