/**
 * dsh-knowledge-sqlite — model-facing tools（knowledge_*）+ 验证工具（knowledge_probe）。
 *
 * 契约与 V1.11 一致：
 *  - 打标字段不在参数里（工具层所有权：服务从执行上下文派生）
 *  - write/update/delete 的 ask 门控在 index.ts（tools/pre-execute）
 *  - knowledge_probe 为实验套件 e2e 载体（阶段 3 验收门禁）
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { Context } from '@deepseek-ai/cordis'
import type { KnowledgeService } from './index.ts'
import type { Scope, ScopeFilter } from './types.ts'

const renderJson = (_args: unknown, value: unknown): Array<{ type: 'text'; text: string }> => [
  { type: 'text', text: JSON.stringify(value, null, 2) },
]

export function registerKnowledgeTools(
  ctx: Context,
  service: KnowledgeService,
  options: { registerProbeTool?: boolean } = {},
): void {
  ctx.tools.register(defineTool({
    name: 'knowledge_write',
    description: '写入一条跨会话知识（V1.11 契约）。写入即入 SQLite FTS5 trigram 词法索引，零 LLM，立即可检索。'
      + '跨会话持久变更：受 ask 门控（需要用户确认）。dedupeKey 相同则 upsert（id 不变）。'
      + 'scope=global 需要 allowedGlobalWriters 成员资格；scope=session 为会话私有草稿。',
    parameters: {
      content: { type: 'string', required: true, description: '知识正文（maxContentTokens 超限 write-rejected）' },
      scope: { type: 'string', enum: ['workspace', 'session', 'global'], description: '默认 workspace' },
      dedupeKey: { type: 'string', description: 'upsert 键；唯一性 (workspace, scope, dedupeKey)；写后不可变' },
      importance: { type: 'number', description: '1-10，默认 5' },
      tags: { type: 'json', description: '标签数组' },
      ttl: { type: 'number', description: 'TTL 秒数；过期条目从检索过滤，list 标记 expired' },
      source: { type: 'json', description: '溯源 { sessionId, seq }' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args) {
      return service.write({
        content: args.content,
        scope: args.scope as Scope | undefined,
        dedupeKey: args.dedupeKey,
        importance: args.importance,
        ttl: args.ttl,
        tags: Array.isArray(args.tags) ? (args.tags as string[]) : undefined,
        source: args.source as { sessionId: string; seq: number } | undefined,
      })
    },
  }))

  ctx.tools.register(defineTool({
    name: 'knowledge_update',
    description: '修正一条知识的内容/字段（V1.11 契约）。保留 id/溯源/打标；scope 与 dedupeKey 写后不可变。',
    parameters: {
      id: { type: 'string', required: true, description: '知识条目 id' },
      content: { type: 'string', description: '新正文（更新后标记 needsEnrichment）' },
      importance: { type: 'number', description: '1-10' },
      tags: { type: 'json', description: '标签数组' },
      ttl: { type: 'number', description: 'TTL 秒数；null 清除' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args) {
      return service.update({
        id: args.id,
        content: args.content,
        importance: args.importance,
        ttl: args.ttl,
        tags: Array.isArray(args.tags) ? (args.tags as string[]) : undefined,
      })
    },
  }))

  ctx.tools.register(defineTool({
    name: 'knowledge_search',
    description: '检索跨会话知识（V1.11 契约）。SQLite FTS5 trigram（中文子串）+ BM25；默认 L1 查询扩展'
      + '（一次小模型调用，按归一化查询缓存，超时降级 degraded:"lexical" 而非报错）。'
      + 'expand:false 或传 variants 跳过扩展调用。命中带 provenance（original/enriched）与 authorTier。',
    parameters: {
      query: { type: 'string', required: true, description: '查询文本（中文子串 ≥3 字符可命中）' },
      scope: { type: 'string', enum: ['workspace', 'session', 'global', 'all'], description: '过滤范围' },
      expand: { type: 'boolean', description: 'L1 查询扩展，默认 true' },
      variants: { type: 'json', description: '调用方提供的扩展变体（跳过扩展调用）' },
      budget: { type: 'json', description: '{ maxItems?, maxTokens? } 预算截断' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args, exec) {
      const result = await service.search(args.query, {
        scope: args.scope as ScopeFilter | undefined,
        expand: args.expand,
        variants: Array.isArray(args.variants) ? (args.variants as string[]) : undefined,
        budget: args.budget as { maxTokens?: number; maxItems?: number } | undefined,
        signal: exec.signal,
      })
      return result as unknown as JsonValue
    },
  }))

  ctx.tools.register(defineTool({
    name: 'knowledge_list',
    description: '列出/审计知识条目（V1.11 契约）。游标分页（新条目在前）；过期条目带 expired:true；'
      + '删除条目需要 includeDeleted。',
    parameters: {
      scope: { type: 'string', enum: ['workspace', 'session', 'global', 'all'], description: '过滤范围，默认 all' },
      cursor: { type: 'string', description: '分页游标' },
      limit: { type: 'number', description: '每页条数，默认 50，上限 200' },
      includeDeleted: { type: 'boolean', description: '包含已删除条目' },
      includeExpired: { type: 'boolean', description: '包含过期条目（默认不含）' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args) {
      const result = await service.list((args.scope ?? 'all') as ScopeFilter, args)
      return result as unknown as JsonValue
    },
  }))

  ctx.tools.register(defineTool({
    name: 'knowledge_delete',
    description: '删除一条知识（V1.11 契约）。tombstone（搜索过滤、list 可见带 deleted:true）。'
      + '跨会话持久变更：受 ask 门控。过期条目 delete 返回 false。',
    parameters: {
      id: { type: 'string', required: true, description: '知识条目 id' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args) {
      return service.delete(args.id)
    },
  }))

  if (options.registerProbeTool !== false) ctx.tools.register(defineTool({
    name: 'knowledge_probe',
    description: '实验套件验证工具（阶段 3 门禁）：seed 装载 memory-experiment 语料，评估 hard/human 查询集'
      + ' A/C/D/L1-live 臂 recall@1 与 precision@1（信息性），human 套件含 none 查询无误报检查，跑契约检查。'
      + 'suite: seed|hard|human|contract|all',
    parameters: {
      suite: { type: 'string', required: true, enum: ['seed', 'hard', 'human', 'contract', 'latency', 'variance', 'all'], description: '验证阶段' },
      fresh: { type: 'boolean', description: '清空 L1 扩展缓存后执行（单轮独立扩展）' },
      runs: { type: 'number', description: 'variance 套件的运行轮数，默认 10（每轮清缓存独立扩展）' },
    },
    output: { schema: { type: 'json' }, render: renderJson },
    async execute(args) {
      const result = await service.probe(
        args.suite as 'seed' | 'hard' | 'human' | 'contract' | 'latency' | 'variance' | 'all',
        { fresh: args.fresh === true, runs: typeof args.runs === 'number' ? args.runs : 10 },
      )
      return result as unknown as JsonValue
    },
  }))
}

/** 工具注册时暴露的 scope 类型引用（供类型检查）。 */
export type { Scope }
