/**
 * dsh-knowledge-sqlite — V1.11 seam contract 类型。
 *
 * npm 版 schemastery（3.18.1 fork）API 缺口记录：无 `enum`/`nullable`/`z.infer`/`.optional()`。
 * 对策（dsh-session-health 同款）：schema 对象仅作契约文档与未来 Remote 生成素材，
 * 字段不声明 optional（缺实例方法）；TS 类型手写，可选字段用 `?`。
 */
import z from '@deepseek-ai/schemastery'

// ---------- 枚举（z.const 组合；运行期校验） ----------
export const Scope = z.union([z.const('workspace'), z.const('session'), z.const('global')])
export type Scope = 'workspace' | 'session' | 'global'

export const ScopeFilter = z.union([z.const('workspace'), z.const('session'), z.const('global'), z.const('all')])
export type ScopeFilter = 'workspace' | 'session' | 'global' | 'all'

export const AuthorTier = z.union([z.const('human'), z.const('explicit'), z.const('derived'), z.const('llm')])
export type AuthorTier = 'human' | 'explicit' | 'derived' | 'llm'

// ---------- 输入 ----------
export interface KnowledgeSource {
  sessionId: string
  seq: number
}
export const KnowledgeSourceSchema = z.object({
  sessionId: z.string(),
  seq: z.number(),
})

/**
 * 写入输入。打标字段（workspaceId/ownerId/authorTier）不在其中——
 * 工具层派生并打标，调用方伪造 → write-rejected（V1.11）。
 */
export interface KnowledgeItemInput {
  content: string // maxContentTokens 在 write 处校验
  scope?: Scope
  source?: KnowledgeSource
  importance?: number // 1-10，默认 5
  tags?: string[]
  dedupeKey?: string // upsert 键；(workspace, scope, dedupeKey) 唯一；写后不可变
  ttl?: number // 秒
}
export const KnowledgeItemInputSchema = z.object({
  content: z.string(),
  scope: Scope,
  source: KnowledgeSourceSchema,
  importance: z.number(),
  tags: z.array(z.string()),
  dedupeKey: z.string(),
  ttl: z.number(),
})

export interface KnowledgeUpdateInput {
  id: string
  content?: string
  importance?: number
  tags?: string[]
  ttl?: number | null // null 清除 TTL
}

export interface SearchOptions {
  scope?: ScopeFilter
  path?: string // 预留：workspace 内细分（phase 1 接受 no-op）
  budget?: { maxTokens?: number; maxItems?: number }
  expand?: boolean // L1 查询扩展；模型工具路径默认 true，注入路径默认 false
  variants?: string[] // 调用方提供的扩展变体（跳过扩展调用）
  signal?: AbortSignal
}
export const SearchOptionsSchema = z.object({
  scope: ScopeFilter,
  path: z.string(),
  budget: z.object({ maxTokens: z.number(), maxItems: z.number() }),
  expand: z.boolean(),
  variants: z.array(z.string()),
})

export interface ListOptions {
  cursor?: string
  limit?: number // 默认 50，上限 200
  includeDeleted?: boolean
  includeExpired?: boolean
}

// ---------- 输出 ----------
export interface KnowledgeHit {
  id: string
  content: string
  score: number
  snippet: string
  provenance?: 'original' | 'enriched' // 片段匹配窗口来自哪个字段
  authorTier?: AuthorTier
}

export interface KnowledgeMeta {
  id: string
  content: string
  scope: Scope
  authorTier: AuthorTier
  importance: number
  dedupeKey: string | null
  ttlSeconds: number | null
  createdAt: number
  updatedAt: number
  expired: boolean
  deleted: boolean
}

export interface KnowledgeListResult {
  items: KnowledgeMeta[]
  nextCursor?: string
}

/** 错误语义（镜像 DomainError 风格）：closed / missing-key / write-rejected。 */
export type KnowledgeErrorCode = 'closed' | 'missing-key' | 'write-rejected'
export interface KnowledgeError {
  error: { code: KnowledgeErrorCode; message: string }
}
export type KnowledgeResult<T> = T | KnowledgeError

export interface KnowledgeSearchResult {
  hits: KnowledgeHit[]
  /** L1 超时/失败时降级为纯词法，元数据标记（不是工具错误）。 */
  degraded: 'lexical' | null
  expansion?: {
    used: boolean
    source: 'live' | 'cache' | 'caller' | null
    degraded: boolean
    latencyMs: number
    variantsCount: number
  }
}

/** 打标字段：工具层所有权（调用方身份派生）。 */
export interface KnowledgeStamps {
  workspaceId: string
  ownerId: string
  authorTier: AuthorTier
}

/** 检索表选择（内部）：base=仅原文（L0/L1），rich=原文+富化（L2）。 */
export type KnowledgeTable = 'base' | 'rich'
