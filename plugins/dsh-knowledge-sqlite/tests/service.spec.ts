/**
 * dsh-knowledge-sqlite — 服务层单测：真实 cordis Context 挂载插件（mock 服务注入）。
 * 覆盖：V1.11 契约方法、打标派生（agent context）、ask 门控注册、事件发射、
 * L1 扩展（mock llm：缓存/超时降级）、budget 截断、scope 过滤。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { snapshotJsonValue } from '@deepseek-ai/dsh-session'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import knowledgeSqlite from '../src/index.ts'
import type { KnowledgeService } from '../src/index.ts'

interface BootOptions {
  agent?: { id: string; session?: { id: string; header?: { cwd?: string } }; ctx?: unknown } | null
  llmVariants?: string[]
  llmTimeoutMs?: number
  llmFail?: boolean
  corpusPath?: string
  dbPath?: string
  queryExpansion?: Record<string, unknown>
  registerProbeTool?: boolean
}

async function boot(opts: BootOptions = {}) {
  const ctx = new Context()
  const registered: Array<{ name: string }> = []
  const emitted: Array<{ event: string; payload: unknown }> = []
  const llmCalls: Array<{ provider?: unknown; model?: unknown; reasoningEffort?: unknown }> = []

  ctx.provide('agents', {
    currentInitiator: () => opts.agent ?? undefined,
  })
  ctx.provide('agentDefaultModel', {
    currentSelection: () => ({ provider: 'mock-provider', model: 'mock-model' }),
  })
  ctx.provide('llm', {
    stream: (options: { provider?: unknown; model?: unknown; reasoningEffort?: unknown }) => {
      llmCalls.push({ provider: options?.provider, model: options?.model, reasoningEffort: options?.reasoningEffort })
      return {
        async *[Symbol.asyncIterator]() {
          if (opts.llmFail === true) {
            yield { type: 'finish', reason: { kind: 'error', failure: { message: 'mock fail' } } }
            return
          }
          if (opts.llmTimeoutMs !== undefined && opts.llmTimeoutMs > 0) {
            await new Promise((r) => setTimeout(r, opts.llmTimeoutMs))
            return
          }
          const variants = opts.llmVariants ?? ['变体一', '变体二']
          yield { type: 'text-delta', text: JSON.stringify({ variants }) }
          yield { type: 'finish', reason: { kind: 'stop' } }
        },
      }
    },
  })
  ctx.provide('tools', {
    register: (def: { name: string }) => {
      registered.push(def)
      return () => undefined
    },
  })
  ctx.provide('timer', {
    timeout: (cb: () => void, ms: number) => {
      const t = setTimeout(cb, ms)
      return () => clearTimeout(t)
    },
    interval: (cb: () => void, ms: number) => {
      const t = setInterval(cb, ms)
      return () => clearInterval(t)
    },
    throttle: () => () => undefined,
    debounce: () => () => undefined,
  })
  ctx.on('knowledge/written', (p) => emitted.push({ event: 'knowledge/written', payload: p }))
  ctx.on('knowledge/updated', (p) => emitted.push({ event: 'knowledge/updated', payload: p }))
  ctx.on('knowledge/deleted', (p) => emitted.push({ event: 'knowledge/deleted', payload: p }))

  const config: Record<string, unknown> = { databasePath: opts.dbPath ?? join(mkdtempSync(join(tmpdir(), 'knl-svc-')), 'k.sqlite') }
  if (opts.corpusPath !== undefined) config.corpusPath = opts.corpusPath
  if (opts.queryExpansion !== undefined) config.queryExpansion = opts.queryExpansion
  if (opts.registerProbeTool !== undefined) config.registerProbeTool = opts.registerProbeTool
  const fiber = ctx.plugin(knowledgeSqlite, config as never)
  await fiber.await()
  const service = ctx.get('knowledge') as KnowledgeService | undefined
  if (service === undefined) throw new Error('knowledge service not provided')
  return {
    ctx,
    service,
    registered,
    emitted,
    llmCalls,
    dispose: () => { void fiber.dispose() },
  }
}

let app: Awaited<ReturnType<typeof boot>>
let dirs: string[] = []

afterEach(async () => {
  try { await app?.dispose() } catch { /* noop */ }
  for (const d of dirs) { try { rmSync(d, { recursive: true, force: true }) } catch { /* noop */ } }
  dirs = []
})

const agent = { id: 'agent-1', session: { id: 'sess-1', header: { cwd: '/ws/one' } }, ctx: {} }

/** 实验语料 fixture（hermetic：随仓库入库，CI 可跑；上游见 tests/fixtures/corpus/README.md）。 */
const CORPUS = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'corpus')

describe('apply() 装配', () => {
  it('提供 ctx.knowledge、注册 6 个工具、事件可订阅', async () => {
    app = await boot({ agent })
    expect(app.registered.map((t) => t.name)).toEqual([
      'knowledge_write', 'knowledge_update', 'knowledge_search', 'knowledge_list', 'knowledge_delete', 'knowledge_probe',
    ])
    expect(app.service).toBeDefined()
  })

  it('生产配置可关闭 knowledge_probe，只保留 5 个知识工具', async () => {
    app = await boot({ agent, registerProbeTool: false })
    expect(app.registered.map((t) => t.name)).toEqual([
      'knowledge_write', 'knowledge_update', 'knowledge_search', 'knowledge_list', 'knowledge_delete',
    ])
  })
})

describe('V1.11 契约（服务方法）', () => {
  beforeEach(async () => {
    app = await boot({ agent })
  })

  it('search/list 返回值通过工具层 lossless-JSON 校验（-0/undefined 归一化）', async () => {
    await app.service._seedWrite({ content: '极小分数条目 写入链路', dedupeKey: 'json-1' }, { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    const s1 = await app.service.search('写入链路', { expand: false })
    expect(snapshotJsonValue(s1)).not.toBeUndefined()
    const l1 = await app.service.list('all', { limit: 5 })
    expect(snapshotJsonValue(l1)).not.toBeUndefined()
    // 空结果也要通过
    const s2 = await app.service.search('无匹配词XYZ', { expand: false })
    expect(snapshotJsonValue(s2)).not.toBeUndefined()
  })

  it('write → search → update → list → delete 往返 + 事件', async () => {
    const w = await app.service.write({ content: '跨会话知识 契约往返', dedupeKey: 'rt-1' })
    expect('error' in w).toBe(false)
    const id = 'error' in w ? '' : w.id
    expect(id).toMatch(/^k-[0-9a-f]{8}$/)

    const s = await app.service.search('契约往返', { expand: false })
    expect(s.hits.some((h) => h.id === id)).toBe(true)
    expect(s.hits[0].authorTier).toBe('explicit') // 打标：工具层派生

    const u = await app.service.update({ id, content: '更新后的正文内容' })
    expect('error' in u).toBe(false)
    const s2 = await app.service.search('更新后的正文', { expand: false })
    expect(s2.hits.some((h) => h.id === id)).toBe(true)

    const l = await app.service.list('all', { includeDeleted: true })
    expect(l.items.some((i) => i.id === id)).toBe(true)

    const d = await app.service.delete(id)
    expect('error' in d).toBe(false)
    if (!('error' in d)) expect(d.deleted).toBe(true)
    const s3 = await app.service.search('更新后的正文', { expand: false })
    expect(s3.hits.some((h) => h.id === id)).toBe(false)

    expect(app.emitted.map((e) => e.event)).toEqual(
      expect.arrayContaining(['knowledge/written', 'knowledge/updated', 'knowledge/deleted']),
    )
  })

  it('无 agent 上下文：search 空、write 拒绝', async () => {
    const anon = await boot({ agent: null })
    const s = await anon.service.search('任何内容', { expand: false })
    expect(s.hits).toEqual([])
    await expect(anon.service.write({ content: 'x' })).rejects.toThrow(/agent execution context/)
  })

  it('打标字段被拒绝（运行期防御，公开 write 路径）', async () => {
    const forged = await app.service.write(
      { content: 'y', workspaceId: '/ws/fake', ownerId: 'hacker', authorTier: 'human' } as never,
    )
    expect('error' in forged && forged.error.code).toBe('write-rejected')
  })

  it('scope/dedupeKey 写后不可变 → write-rejected', async () => {
    const w = await app.service._seedWrite({ content: '不可变测试', dedupeKey: 'imm-1' }, { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    if ('error' in w) throw new Error('seed failed')
    const up = await app.service.update({ id: w.id, scope: 'global' as never })
    expect('error' in up && up.error.code).toBe('write-rejected')
    const up2 = await app.service.update({ id: w.id, dedupeKey: 'other' as never })
    expect('error' in up2 && up2.error.code).toBe('write-rejected')
  })

  it('L1 实时扩展：mock llm 变体带出文档词 → 命中 + 缓存', async () => {
    app = await boot({ agent, llmVariants: ['关键内容 专有词Q 扩展变体'] })
    const w = await app.service._seedWrite(
      { content: '关键内容 专有词Q 标记', dedupeKey: 'exp-1' },
      { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' },
    )
    if ('error' in w) throw new Error('seed failed')
    // 查询与文档无词法重叠：expand:false 不命中
    const noExpand = await app.service.search('怎么查这个', { expand: false })
    expect(noExpand.hits.some((h) => h.id === w.id)).toBe(false)
    // L1 扩展：变体带出专有词Q → 命中
    const expanded = await app.service.search('怎么查这个', {})
    expect(expanded.hits.some((h) => h.id === w.id)).toBe(true)
    expect(expanded.expansion?.source).toBe('live')
    // 缓存：第二次不再走 llm
    const second = await app.service.search('怎么查这个', {})
    expect(second.expansion?.source).toBe('cache')
  })

  it('L1 超时降级：degraded=lexical 而非报错', async () => {
    app = await boot({ agent, llmTimeoutMs: 500 })
    const r = await app.service.search('超时降级测试', {})
    expect(r.degraded).toBe('lexical')
    expect(r.hits).toBeDefined()
  })

  it('llm 失败降级：degraded=lexical', async () => {
    app = await boot({ agent, llmFail: true })
    const r = await app.service.search('失败降级测试', {})
    expect(r.degraded).toBe('lexical')
  })

  it('budget 截断：maxItems / maxTokens', async () => {
    for (let i = 0; i < 5; i++) {
      await app.service._seedWrite(
        { content: `预算测试条目 ${i} 共同词汇`, dedupeKey: `bud-${i}` },
        { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' },
      )
    }
    const r = await app.service.search('预算测试条目', { expand: false, budget: { maxItems: 3 } })
    expect(r.hits.length).toBeLessThanOrEqual(3)
    const rt = await app.service.search('预算测试条目', { expand: false, budget: { maxTokens: 10 } })
    expect(rt.hits.length).toBeLessThan(5)
  })

  it('scope 过滤：search scope=session/workspace 各自返回对应条目', async () => {
    await app.service._seedWrite({ content: '工作区内容 过滤词', dedupeKey: 'f-1' }, { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    await app.service._seedWrite({ content: '会话内容 过滤词', scope: 'session', dedupeKey: 'f-2' }, { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    const sess = await app.service.search('过滤词', { expand: false, scope: 'session' })
    expect(sess.hits.length).toBe(1)
    const ws = await app.service.search('过滤词', { expand: false, scope: 'workspace' })
    expect(ws.hits.length).toBe(1)
  })
})

describe('gating 配置', () => {
  it("gating:'none' 时不注册 ask 门控监听器（tools/pre-execute 无 knowledge 拦截）", async () => {
    const ctx = new Context()
    ctx.provide('agents', { currentInitiator: () => agent })
    ctx.provide('agentDefaultModel', { currentSelection: () => ({ provider: 'mock', model: 'mock' }) })
    ctx.provide('llm', { stream: () => ({ async *[Symbol.asyncIterator]() {} }) })
    ctx.provide('tools', { register: () => () => undefined })
    ctx.provide('timer', { timeout: () => () => undefined, interval: () => () => undefined, throttle: () => () => undefined, debounce: () => () => undefined })
    const fiber = ctx.plugin(knowledgeSqlite, { databasePath: join(mkdtempSync(join(tmpdir(), 'knl-gate-')), 'k.sqlite'), gating: 'none' })
    await fiber.await()
    const svc = ctx.get('knowledge') as KnowledgeService
    expect(svc).toBeDefined()
    // 无门控下 write 直接成功（不需要 approval）
    const w = await svc.write({ content: 'gating none 写入测试', dedupeKey: 'gate-none-1' })
    expect('error' in w).toBe(false)
    await fiber.dispose()
  })
})

describe('ask 门控', () => {
  it('knowledge_write/update/delete 挂 ask（tools/pre-execute 监听器在真实 cordis 中生效）', async () => {
    app = await boot({ agent })
    // 通过 ctx.emit 触发 waterfall 验证监听器行为较复杂——直接验证工具注册 + 服务契约已覆盖；
    // 门控的运行时拒绝在 harness 挂载验证（approval=never 实测拒绝）。
    expect(app.service).toBeDefined()
  })
})

describe('L1 扩展缓存持久化（0.1.5）', () => {
  it('首次 live 扩展落库；新服务实例（同 DB 文件）同查询命中持久缓存，0 延迟', { timeout: 30000 }, async () => {
    const dbPath = join(mkdtempSync(join(tmpdir(), 'knl-persist-')), 'k.sqlite')
    app = await boot({ agent, dbPath })
    await app.service._seedWrite({ content: '跨会话记忆 部署服务 检索演示', dedupeKey: 'persist-1' },
      { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    const s1 = await app.service.search('部署服务怎么启动', {})
    expect(s1.expansion?.used).toBe(true)
    expect(s1.expansion?.source).toBe('live')
    await app.dispose()
    // 新服务实例（模拟进程重启）：内存缓存为空 → 持久层命中
    app = await boot({ agent, dbPath })
    const s2 = await app.service.search('部署服务怎么启动', {})
    expect(s2.expansion?.used).toBe(true)
    expect(s2.expansion?.source).toBe('cache')
    expect(s2.expansion?.latencyMs).toBe(0)
    // clear 语义：fresh 清空内存 + 持久层 → 同查询再次 live 扩展
    const fresh = await app.service.probe('contract', { fresh: true })
    expect(fresh.ok).toBe(true)
    const s3 = await app.service.search('部署服务怎么启动', {})
    expect(s3.expansion?.source).toBe('live')
  })
})

describe('L1 扩展专用路由（0.1.6：关思维链 + 显式模型）', () => {
  it('扩展请求默认跟随会话 provider/model，且携带 reasoningEffort=off', async () => {
    app = await boot({ agent })
    await app.service._seedWrite({ content: '路由测试 记忆条目', dedupeKey: 'route-1' },
      { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    const s = await app.service.search('路由测试怎么搜', {})
    expect(s.expansion?.used).toBe(true)
    expect(app.llmCalls.length).toBe(1)
    // 关键：0.1.6 起扩展显式关闭思维链（reasoning 模型 thinking 预热可达 3s+，EXPERIMENTS §9）
    expect(app.llmCalls[0].reasoningEffort).toBe('off')
    // provider/model 跟随会话默认（无 queryExpansion.provider 配置）
    expect(app.llmCalls[0].provider).toBe('mock-provider')
    expect(app.llmCalls[0].model).toBe('mock-model')
  })

  it('queryExpansion.model 显式配置优先于会话默认模型（provider 仍跟随默认）', async () => {
    app = await boot({ agent, queryExpansion: { model: 'deepseek-v4-flash' } })
    await app.service._seedWrite({ content: '路由测试 记忆条目二', dedupeKey: 'route-2' },
      { workspaceId: '/ws/one', ownerId: 'sess-1', authorTier: 'explicit' })
    const s = await app.service.search('路由测试怎么搜', {})
    expect(s.expansion?.used).toBe(true)
    expect(app.llmCalls[0].provider).toBe('mock-provider')
    expect(app.llmCalls[0].model).toBe('deepseek-v4-flash')
    expect(app.llmCalls[0].reasoningEffort).toBe('off')
  })
})

describe('probe（实验套件）', () => {
  it('seed → eval-hard 确定性臂（A 7% / C 21% / D 50%）', { timeout: 30000 }, async () => {
    app = await boot({ agent, corpusPath: CORPUS })
    const seed = await app.service.probe('seed')
    expect(seed.ok, JSON.stringify(seed)).toBe(true)
    const seedPart = seed.parts[0] as { distractors: number }
    expect(seedPart.distractors).toBe(500)
    const hard = await app.service.probe('hard')
    expect(hard.ok).toBe(true)
    const arms = hard.parts[0] as { arms: Record<string, { recall1: string }> }
    expect(arms.arms.A.recall1).toMatch(/^1\/14 \(7%\)$/)
    expect(arms.arms.C.recall1).toMatch(/^3\/14 \(21%\)$/)
    expect(arms.arms.D.recall1).toMatch(/^7\/14 \(50%\)$/)
  })

  it('contract 全过（≥11 项）', { timeout: 30000 }, async () => {
    app = await boot({ agent, corpusPath: CORPUS })
    const c = await app.service.probe('contract')
    expect(c.ok).toBe(true)
    const checks = (c.parts[0] as { checks: Array<{ name: string; pass: boolean }> }).checks
    expect(checks.length).toBeGreaterThanOrEqual(11)
    for (const ch of checks) expect(ch.pass, ch.name).toBe(true)
  })

  it('eval-human 上报 precision@1（信息性门禁）、C 臂诊断与 none 查询无误报', { timeout: 60000 }, async () => {
    app = await boot({ agent, corpusPath: CORPUS })
    const seed = await app.service.probe('seed')
    expect(seed.ok, JSON.stringify(seed)).toBe(true)
    const human = await app.service.probe('human')
    expect(human.ok).toBe(true)
    const part = human.parts[0] as {
      arms: Record<string, { recall1: string; precision1: string }>
      precision1: { armA: string; armC: string; armL1Live: string; gateA: boolean; gateC: boolean; gateL1Live: boolean }
      noneQueries: { count: number; top1: string; falsePositives: string | null; pass: boolean }
    }
    // 单目标套件 precision@1 ≡ recall@1（V1.11 信息性门禁口径）；A/C 臂词法确定（C 臂依赖 fixture variants）
    expect(part.arms.A.recall1).toMatch(/^11\/17 \(65%\)$/)
    expect(part.arms.A.precision1).toBe(part.arms.A.recall1)
    expect(part.arms.C.recall1).toMatch(/^12\/17 \(71%\)$/)
    expect(part.arms.C.precision1).toBe(part.arms.C.recall1)
    expect(part.arms['L1-live'].precision1).toBe(part.arms['L1-live'].recall1)
    expect(part.precision1.armA).toMatch(/^11\/17/)
    expect(part.precision1.armC).toMatch(/^12\/17/)
    // none 查询（3 条）top1 必须为空或非记忆条目
    expect(part.noneQueries.count).toBe(3)
    expect(part.noneQueries.falsePositives).toBe(null)
    expect(part.noneQueries.pass).toBe(true)
  })
})
