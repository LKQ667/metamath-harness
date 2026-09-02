/**
 * dsh-knowledge-sqlite — cross-session knowledge for DeepSeek Harness.
 *
 * 单 bundle（执行计划阶段 1 决策）：ctx.knowledge 服务注册（V1.11 契约）
 * + SQLite FTS5 trigram provider + knowledge_* 工具 + L1 查询扩展 + 实验套件探针。
 *
 * 授权：workspace 隔离（调用方 cwd 身份）+ ask 门控（tools/pre-execute）
 * + allowedGlobalWriters（global scope 写）。
 * 信任：authorTier 四档，打标字段工具层所有（服务从执行上下文派生，绝不来自调用方参数）。
 */
import { Service } from '@deepseek-ai/cordis'
import type { Context } from '@deepseek-ai/cordis'
import { homedir } from 'node:os'
import { isAbsolute, join } from 'node:path'
import { SqliteKnowledgeStore } from './store.ts'
import type { StoredItem } from './store.ts'
import { QueryExpander } from './expand.ts'
import { estimateTokens, provenanceOf, queryGrams, snippetOf } from './search.ts'
import type {
  AuthorTier,
  KnowledgeHit,
  KnowledgeListResult,
  KnowledgeSearchResult,
  KnowledgeStamps,
  Scope,
  ScopeFilter,
} from './types.ts'
import { registerKnowledgeTools } from './tools.ts'
import { runProbe } from './probe.ts'

// ---------- 配置（V1.11 配置 schema 的插件落地；可选，默认值即提案默认） ----------
export interface KnowledgeSqliteConfig {
  /** 持久变更门控：'ask'（默认）对 write/update/delete 请求确认；'none' 跳过门控 */
  gating?: 'ask' | 'none'
  /** 是否注册实验语料探针；生产环境建议关闭，默认保持上游行为 */
  registerProbeTool?: boolean
  /** SQLite 数据库路径；默认 $DSH_HOME/knowledge.sqlite */
  databasePath?: string
  /** probe 语料目录；默认 '<workspace>/research/memory-knowledge-seam/experiments/memory-experiment'（实验套件） */
  corpusPath?: string
  /** seam 级写上限（V1.11 enrichment.maxContentTokens，默认 2048） */
  maxContentTokens?: number
  queryExpansion?: {
    enabled?: boolean
    model?: string
    maxOutputTokens?: number
    timeoutMs?: number
    cache?: boolean
  }
  retrieval?: {
    topN?: number
    maxQueryTrigrams?: number
    maxCandidates?: number
  }
  authorization?: {
    allowedGlobalWriters?: string[]
  }
}

export interface ResolvedConfig {
  gating: 'ask' | 'none'
  registerProbeTool: boolean
  databasePath: string
  corpusPath: string
  maxContentTokens: number
  queryExpansion: { enabled: boolean; model?: string; maxOutputTokens: number; timeoutMs: number; cache: boolean }
  retrieval: { topN: number; maxQueryTrigrams: number; maxCandidates: number }
  authorization: { allowedGlobalWriters: string[] }
}

export function defaultDbPath(): string {
  const home = process.env.DSH_HOME ?? join(homedir(), '.dsh')
  return join(home, 'knowledge.sqlite')
}

// ---------- 服务 ----------
export type WriteResult = { id: string; wasUpdate: boolean; scope: Scope; importance: number } | { error: { code: 'closed' | 'missing-key' | 'write-rejected'; message: string } }

export class KnowledgeService extends Service {
  static inject = ['agents']

  private readonly store: SqliteKnowledgeStore
  private readonly expander: QueryExpander
  private readonly config: ResolvedConfig

  constructor(ctx: Context, store: SqliteKnowledgeStore, expander: QueryExpander, config: ResolvedConfig) {
    super(ctx, 'knowledge')
    this.store = store
    this.expander = expander
    this.config = config
  }

  // ============ 调用方派生（工具层所有权：打标字段来自执行上下文，绝不来自参数） ============
  private caller(): { stamps: KnowledgeStamps; sessionId: string; actorId: string } | null {
    const agents = this.ctx.get('agents') as { currentInitiator(): { id: string; session?: { id?: string; header?: { cwd?: string } }; ctx: Context } | undefined } | undefined
    const agent = agents?.currentInitiator()
    if (agent === undefined || agent === null) return null
    let workspaceId: string | null = null
    try { workspaceId = agent.session?.header?.cwd ?? null } catch { workspaceId = null }
    if (workspaceId === null || workspaceId === undefined) return null
    const sessionId = agent.session?.id ?? agent.id
    // global 写 allowlist 的 actor：agent/preset id（V1.11：稳定跨会话重建）
    let presetId: string | undefined
    try {
      const presets = this.ctx.get('agentPresets') as { composedPreset(ctx: Context): string | undefined } | undefined
      presetId = presets?.composedPreset(agent.ctx)
    } catch {
      presetId = undefined
    }
    return {
      stamps: { workspaceId, ownerId: sessionId, authorTier: 'explicit' },
      sessionId,
      actorId: presetId ?? agent.id,
    }
  }

  private requireCaller(): { stamps: KnowledgeStamps; sessionId: string; actorId: string } {
    const caller = this.caller()
    if (caller === null) {
      throw Object.assign(new Error('knowledge requires an agent execution context'), { code: 'write-rejected' })
    }
    return caller
  }

  private readCaller(): { stamps: KnowledgeStamps; sessionId: string; actorId: string } | null {
    return this.caller()
  }

  /** 发射 knowledge/* 事件（自定义事件名，绕过 cordis Events 键类型）。 */
  private emit(name: string, payload: unknown): void {
    ;(this.ctx as unknown as { emit(event: string, data: unknown): void }).emit(name, payload)
  }

  // ============ V1.11 契约 ============
  async write(input: {
    content: string
    scope?: Scope
    source?: { sessionId: string; seq: number } | null
    importance?: number
    tags?: string[]
    dedupeKey?: string
    ttl?: number
  }): Promise<WriteResult> {
    const caller = this.requireCaller()
    return this.doWrite(input, caller)
  }

  async update(input: { id: string; content?: string; importance?: number; tags?: string[]; ttl?: number | null }): Promise<{ updated: boolean } | { error: { code: string; message: string } }> {
    const caller = this.requireCaller()
    return this.doUpdate(input, caller)
  }

  async search(query: string, opts: {
    scope?: ScopeFilter
    path?: string
    budget?: { maxTokens?: number; maxItems?: number }
    expand?: boolean
    variants?: string[]
    signal?: AbortSignal
  } = {}): Promise<KnowledgeSearchResult> {
    const caller = this.readCaller()
    if (caller === null) return { hits: [], degraded: null }
    return this.doSearch(query, opts, caller, 'items_fts_rich')
  }

  async list(scope: ScopeFilter, opts: { cursor?: string; limit?: number; includeDeleted?: boolean; includeExpired?: boolean } = {}): Promise<KnowledgeListResult> {
    const caller = this.readCaller()
    if (caller === null) return { items: [] }
    const result = this.store.list(scope, opts, { ...caller.stamps, sessionId: caller.sessionId })
    // 工具层 JSON 校验拒绝 undefined 字段
    if (result.nextCursor === undefined) delete result.nextCursor
    return result
  }

  async delete(id: string): Promise<{ deleted: boolean } | { error: { code: string; message: string } }> {
    const caller = this.requireCaller()
    const result = await this.store.delete(id, { ...caller.stamps, sessionId: caller.sessionId })
    if (!('error' in result) && result.deleted === true) {
      const item = this.store.get(id)
      this.emit('knowledge/deleted', { id, scope: item?.scope ?? 'workspace' })
    }
    return result
  }

  // ============ 内部（trusted writer / probe / 测试） ============
  /** Trusted internal writer（V1.11 注册 writer 类：probe 装载/富化回写/评估）。 */
  async _seedWrite(
    input: { content: string; scope?: Scope; dedupeKey?: string; importance?: number; ttl?: number },
    stamps: KnowledgeStamps,
  ): Promise<{ id: string } | { error: { code: string; message: string } }> {
    const actorId = stamps.ownerId
    const result = await this.store.write(
      { content: input.content, scope: input.scope, dedupeKey: input.dedupeKey, importance: input.importance, ttl: input.ttl },
      stamps,
      this.config.authorization.allowedGlobalWriters,
      actorId,
    )
    if ('error' in result) return result
    this.emit('knowledge/written', { id: result.id, scope: result.scope, importance: result.importance })
    return { id: result.id }
  }

  async _seedUpdate(
    id: string,
    patch: { content?: string; importance?: number; tags?: string[]; ttl?: number | null; scope?: never },
    stamps: KnowledgeStamps,
  ): Promise<{ updated: boolean } | { error: { code: string; message: string } }> {
    if (patch.scope !== undefined) {
      return { error: { code: 'write-rejected', message: 'scope/dedupeKey are immutable after write (V1.11)' } }
    }
    const result = await this.store.update(id, patch, { ...stamps, sessionId: stamps.ownerId })
    if ('error' in result) return result
    this.emit('knowledge/updated', { id, scope: 'workspace' })
    return result
  }

  async _seedDelete(id: string, stamps: KnowledgeStamps): Promise<{ deleted: boolean } | { error: { code: string; message: string } }> {
    const result = await this.store.delete(id, { ...stamps, sessionId: stamps.ownerId })
    if ('error' in result) return result
    this.emit('knowledge/deleted', { id, scope: 'workspace' })
    return result
  }

  async _seedList(opts: { cursor?: string; limit?: number; includeDeleted?: boolean; includeExpired?: boolean }, stamps: KnowledgeStamps): Promise<KnowledgeListResult> {
    return this.store.list('all', opts, { ...stamps, sessionId: stamps.ownerId })
  }

  /** 内部检索（probe 评估：table 可为 base/rich；stamps 可覆盖以测隔离）。 */
  async _searchInternal(query: string, opts: {
    table?: 'items_fts_base' | 'items_fts_rich'
    expand?: boolean
    variants?: string[]
    signal?: AbortSignal
  }, stampsOverride?: KnowledgeStamps): Promise<KnowledgeSearchResult> {
    const caller = stampsOverride !== undefined
      ? { stamps: stampsOverride, sessionId: stampsOverride.ownerId, actorId: stampsOverride.ownerId }
      : this.readCaller()
    if (caller === null) return { hits: [], degraded: null }
    const table = opts.table === 'items_fts_base' ? 'items_fts_base' : 'items_fts_rich'
    return this.doSearch(query, opts, caller, table)
  }

  async _dedupeIds(): Promise<Map<string, string>> {
    return this.store.dedupeIds()
  }

  // ============ 内部实现 ============
  private async doWrite(
    input: { content: string; scope?: Scope; source?: { sessionId: string; seq: number } | null; importance?: number; tags?: string[]; dedupeKey?: string; ttl?: number },
    caller: { stamps: KnowledgeStamps; sessionId: string; actorId: string },
  ): Promise<WriteResult> {
    const result = await this.store.write(input, caller.stamps, this.config.authorization.allowedGlobalWriters, caller.actorId)
    if ('error' in result) return result
    this.emit('knowledge/written', { id: result.id, scope: result.scope, importance: result.importance })
    return result
  }

  private async doUpdate(
    input: { id: string; content?: string; importance?: number; tags?: string[]; ttl?: number | null },
    caller: { stamps: KnowledgeStamps; sessionId: string; actorId: string },
  ): Promise<{ updated: boolean } | { error: { code: string; message: string } }> {
    if ((input as { scope?: unknown }).scope !== undefined || (input as { dedupeKey?: unknown }).dedupeKey !== undefined) {
      return { error: { code: 'write-rejected', message: 'scope/dedupeKey are immutable after write (V1.11)' } }
    }
    const result = await this.store.update(input.id, input, { ...caller.stamps, sessionId: caller.sessionId })
    if ('error' in result) return result
    const item = await this.store.get(input.id)
    this.emit('knowledge/updated', { id: input.id, scope: item?.scope ?? 'workspace' })
    return result
  }

  private async doSearch(
    query: string,
    opts: {
      scope?: ScopeFilter
      path?: string
      budget?: { maxTokens?: number; maxItems?: number }
      expand?: boolean
      variants?: string[]
      signal?: AbortSignal
    },
    caller: { stamps: KnowledgeStamps; sessionId: string; actorId: string },
    table: 'items_fts_base' | 'items_fts_rich',
  ): Promise<KnowledgeSearchResult> {
    if (typeof query !== 'string' || query.trim() === '') return { hits: [], degraded: null }
    const expand = opts.expand !== false
    let variants: string[] | null = Array.isArray(opts.variants) ? opts.variants : null
    let expansion: KnowledgeSearchResult['expansion']
    let degraded: 'lexical' | null = null
    if (variants === null && expand && this.config.queryExpansion.enabled) {
      const e = await this.expander.expand(query, opts.signal, caller.stamps.workspaceId)
      variants = e.variants
      if (e.degraded) degraded = 'lexical'
      expansion = { used: true, source: e.source, degraded: e.degraded, latencyMs: e.latencyMs, variantsCount: variants.length }
    } else if (variants !== null && variants.length > 0) {
      expansion = { used: true, source: 'caller', degraded: false, latencyMs: 0, variantsCount: variants.length }
    }
    const texts = variants !== null && variants.length > 0 ? [query, ...variants] : [query]
    const rows = await this.store.search(table === 'items_fts_base' ? 'base' : 'rich', texts, { ...caller.stamps, sessionId: caller.sessionId }, {
      scope: opts.scope,
      topN: this.config.retrieval.topN,
      maxQueryTrigrams: this.config.retrieval.maxQueryTrigrams,
    })
    const maxItems = opts.budget?.maxItems ?? this.config.retrieval.topN
    const qgrams = queryGrams(texts.join(' '))
    const hits: KnowledgeHit[] = []
    let tokens = 0
    for (const r of rows) {
      if (hits.length >= maxItems) break
      const item: StoredItem = r.item
      // score 归一化：Math.round 可能产出 -0（极小 bm25 分数），工具层 JSON 校验拒绝 -0/NaN
      const rounded = Math.round(r.score * 1000) / 1000
      const score = Object.is(rounded, -0) || !Number.isFinite(rounded) ? 0 : rounded
      hits.push({
        id: item.id,
        content: item.content,
        score,
        snippet: snippetOf(item.content, qgrams),
        provenance: provenanceOf(item.content, item.keywords, item.synonyms, item.questions, qgrams),
        authorTier: item.authorTier,
      })
      if (opts.budget?.maxTokens !== undefined) {
        tokens += estimateTokens(item.content)
        if (tokens > opts.budget.maxTokens) break
      }
    }
    // 工具层 JSON 校验拒绝 undefined 字段——返回对象只含已定义字段
    const result: KnowledgeSearchResult = { hits, degraded }
    if (expansion !== undefined) result.expansion = expansion
    return result
  }

  // ============ 实验套件探针（阶段 3 门禁 e2e） ============
  async probe(
    suite: 'seed' | 'hard' | 'human' | 'contract' | 'latency' | 'variance' | 'all',
    opts: { fresh?: boolean; runs?: number } = {},
  ): Promise<{ ok: boolean; parts: Array<Record<string, unknown>> }> {
    // fresh：清扩展缓存——单轮方差需要独立扩展（缓存会杀死随机性）
    if (opts.fresh === true) this.expander.clear()
    const caller = this.readCaller()
    const workspaceId = caller?.stamps.workspaceId
    const corpusPath = workspaceId !== undefined
      ? (isAbsolute(this.config.corpusPath) ? this.config.corpusPath : join(workspaceId, this.config.corpusPath))
      : this.config.corpusPath
    return runProbe({ store: this.store, expander: this.expander, service: this, corpusPath }, suite, caller, opts.runs ?? 10)
  }
}

// ---------- 插件入口 ----------
export const name = 'dsh-knowledge-sqlite'

/**
 * cordis loader 插件形状：loader 的 unwrapExports 后直接 registry.plugin(default)，
 * 函数会被当作插件 body 调用（工厂形态的 default 会被静默忽略——apply 从不执行）。
 * 因此 default 必须是插件对象（inject + apply），config 经 apply 第二参注入。
 */
const knowledgeSqlitePlugin = {
  inject: ['tools', 'agents', 'timer'],
  async apply(ctx: Context, config: KnowledgeSqliteConfig = {}) {
    {
      const resolved: ResolvedConfig = {
        gating: config.gating ?? 'ask',
        registerProbeTool: config.registerProbeTool ?? true,
        databasePath: config.databasePath ?? defaultDbPath(),
        corpusPath: config.corpusPath ?? 'research/memory-knowledge-seam/experiments/memory-experiment',
        maxContentTokens: config.maxContentTokens ?? 2048,
        queryExpansion: {
          enabled: config.queryExpansion?.enabled ?? true,
          model: config.queryExpansion?.model,
          maxOutputTokens: config.queryExpansion?.maxOutputTokens ?? 300,
          timeoutMs: config.queryExpansion?.timeoutMs ?? 3000,
          cache: config.queryExpansion?.cache ?? true,
        },
        retrieval: {
          topN: config.retrieval?.topN ?? 20,
          maxQueryTrigrams: config.retrieval?.maxQueryTrigrams ?? 0, // 0 = 不限（对齐实验基线；生产可设 24，见 README）
          maxCandidates: config.retrieval?.maxCandidates ?? 200,
        },
        authorization: {
          allowedGlobalWriters: config.authorization?.allowedGlobalWriters ?? [],
        },
      }
      const store = await SqliteKnowledgeStore.open(resolved.databasePath, resolved.maxContentTokens)
      ctx.effect(() => () => store.close())
      const expander = new QueryExpander(ctx, {
        enabled: resolved.queryExpansion.enabled,
        model: resolved.queryExpansion.model,
        maxOutputTokens: resolved.queryExpansion.maxOutputTokens,
        timeoutMs: resolved.queryExpansion.timeoutMs,
        cache: resolved.queryExpansion.cache,
      }, {
        get: (wsId, norm) => store.getExpansion(wsId, norm),
        set: (wsId, norm, variants) => store.setExpansion(wsId, norm, variants),
        clear: () => store.clearExpansionCache(),
      })
      const service = new KnowledgeService(ctx, store, expander, resolved)
      // 注：cordis Service 构造器已通过 ctx.reflect.provide 注册 'knowledge'，勿再 ctx.provide
      registerKnowledgeTools(ctx, service, { registerProbeTool: resolved.registerProbeTool })

      // ask 门控（MetaMath 安全适配）：write/update/delete 都是跨会话持久变更，需要用户确认。
      // headless（approval=never）自动拒绝——config gating 替代交互确认。
      // gating: 'none'（部署配置）跳过门控：模型写入自动放行（信任模型场景）。
      if (resolved.gating === 'ask') {
        ctx.on('tools/pre-execute', (exec, next) => {
          if (exec.name === 'knowledge_write' || exec.name === 'knowledge_update' || exec.name === 'knowledge_delete') {
            return Promise.resolve({ kind: 'ask' as const, reason: '知识库写入、更新或删除是跨会话持久变更，需要用户确认' })
          }
          return Promise.resolve(next())
        })
      }
    }
  },
}

export default knowledgeSqlitePlugin

export type { AuthorTier }
