/**
 * dsh-knowledge-sqlite — SQLite provider（V1.11 存储层）。
 *
 * 蓝本：research/memory-knowledge-seam/experiments/prototype/sqlite-trigram-verify.mjs（已验证精确复现 RESULTS-v3 数字）：
 *  - items 表 + 非部分唯一索引 (workspace_id, scope, dedupe_key)（SQLite NULL 互不冲突）
 *  - upsert 用 ON CONFLICT DO UPDATE（保持 rowid 稳定 → FTS rowid 链接有效；
 *    不可用 INSERT OR REPLACE——rowid 变化会断 FTS 链接）
 *  - 双 FTS5 trigram 表：items_fts_base（仅 content）/ items_fts_rich（content+富化拼接）
 *  - 检索：grams OR 化 → MATCH → JOIN items 过滤 deleted/TTL/授权 → bm25 排序 → topN
 */
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { randomUUID } from 'node:crypto'
import type { DatabaseSync } from 'node:sqlite'
import { djb2, docGrams, estimateTokens, matchOf, queryGrams, richTextOf, truncateGrams } from './search.ts'
import type { AuthorTier, KnowledgeListResult, KnowledgeMeta, KnowledgeStamps, KnowledgeTable, Scope } from './types.ts'

/** 一条存储行（含富化字段与溯源）。 */
export interface StoredItem {
  id: string
  scope: Scope
  workspaceId: string
  ownerId: string
  authorTier: AuthorTier
  content: string
  keywords: string | null
  synonyms: string | null
  questions: string | null
  contentHash: string
  importance: number
  tags: string[]
  source: { sessionId: string; seq: number } | null
  dedupeKey: string | null
  ttlSeconds: number | null
  createdAt: number
  updatedAt: number
  deleted: boolean
}

export type StoreResult<T> = T | { error: { code: 'closed' | 'missing-key' | 'write-rejected'; message: string } }

function err(code: 'closed' | 'missing-key' | 'write-rejected', message: string): { error: { code: 'closed' | 'missing-key' | 'write-rejected'; message: string } } {
  return { error: { code, message } }
}

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,
    scope        TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    owner_id     TEXT,
    author_tier  TEXT NOT NULL,
    content      TEXT NOT NULL,
    keywords     TEXT,
    synonyms     TEXT,
    questions    TEXT,
    content_hash TEXT,
    importance   INTEGER NOT NULL DEFAULT 5,
    tags         TEXT,
    source       TEXT,
    dedupe_key   TEXT,
    ttl_seconds  INTEGER,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    deleted      INTEGER NOT NULL DEFAULT 0
  );
  CREATE INDEX IF NOT EXISTS idx_items_scope_ws ON items(scope, workspace_id);
  CREATE UNIQUE INDEX IF NOT EXISTS idx_items_dedupe ON items(workspace_id, scope, dedupe_key);
  CREATE VIRTUAL TABLE IF NOT EXISTS items_fts_base USING fts5(content, tokenize='trigram');
  CREATE VIRTUAL TABLE IF NOT EXISTS items_fts_rich USING fts5(content, tokenize='trigram');
  -- L1 扩展缓存持久化（0.1.5）：按 workspace 隔离；跨进程/重启复用，命中 0 延迟零降级
  CREATE TABLE IF NOT EXISTS expansion_cache (
    ws_id      TEXT NOT NULL,
    query      TEXT NOT NULL,
    variants   TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (ws_id, query)
  );
`

export class SqliteKnowledgeStore {
  private readonly db: DatabaseSync
  private writeChain: Promise<unknown> = Promise.resolve()
  private closed = false
  /** 写入上限（V1.11 enrichment.maxContentTokens 语义：seam 级写上限）。 */
  readonly maxContentTokens: number

  private constructor(db: DatabaseSync, maxContentTokens: number) {
    this.db = db
    this.maxContentTokens = maxContentTokens
  }

  /** 打开（或创建）数据库。node:sqlite 动态 import：Node 22.5+ 无该内置时给出明确错误。 */
  static async open(path: string, maxContentTokens = 2048): Promise<SqliteKnowledgeStore> {
    let DatabaseSyncCtor: typeof DatabaseSync
    try {
      const mod = await import('node:sqlite') as { DatabaseSync: typeof DatabaseSync }
      DatabaseSyncCtor = mod.DatabaseSync
    } catch {
      throw new Error('dsh-knowledge-sqlite: node:sqlite is unavailable — requires Node.js >= 22.5 (or --experimental-sqlite)')
    }
    mkdirSync(dirname(path), { recursive: true })
    const db = new DatabaseSyncCtor(path)
    db.exec(SCHEMA)
    // 迁移：早期库缺 source 列（0.1.0 前的开发库）
    try {
      db.exec('ALTER TABLE items ADD COLUMN source TEXT')
    } catch {
      // 列已存在
    }
    return new SqliteKnowledgeStore(db, maxContentTokens)
  }

  close(): void {
    this.closed = true
    try { this.db.close() } catch { /* idempotent */ }
  }

  // ---------- 写链（V1.11：write/update/delete 串行化） ----------
  private enqueue<T>(fn: () => T): Promise<T> {
    const next = this.writeChain.then(fn, fn)
    this.writeChain = next.catch(() => undefined)
    return next
  }

  // ---------- 内部映射 ----------
  private rowToItem(row: Record<string, unknown>): StoredItem {
    return {
      id: String(row.id),
      scope: row.scope as Scope,
      workspaceId: String(row.workspace_id),
      ownerId: row.owner_id === null ? '' : String(row.owner_id),
      authorTier: row.author_tier as AuthorTier,
      content: String(row.content),
      keywords: row.keywords === null ? null : String(row.keywords),
      synonyms: row.synonyms === null ? null : String(row.synonyms),
      questions: row.questions === null ? null : String(row.questions),
      contentHash: row.content_hash === null ? '' : String(row.content_hash),
      importance: Number(row.importance),
      tags: row.tags === null || row.tags === '' ? [] : JSON.parse(String(row.tags)) as string[],
      source: row.source === null || row.source === undefined || row.source === ''
        ? null
        : JSON.parse(String(row.source)) as { sessionId: string; seq: number },
      dedupeKey: row.dedupe_key === null ? null : String(row.dedupe_key),
      ttlSeconds: row.ttl_seconds === null ? null : Number(row.ttl_seconds),
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
      deleted: Number(row.deleted) === 1,
    }
  }

  private getItem(id: string): StoredItem | undefined {
    const row = this.db.prepare('SELECT * FROM items WHERE id = ?').get(id) as Record<string, unknown> | undefined
    return row === undefined ? undefined : this.rowToItem(row)
  }

  /** 读取单条（服务层事件用；不暴露删除/过期过滤）。 */
  get(id: string): StoredItem | undefined {
    if (this.closed) return undefined
    const item = this.getItem(id)
    return item !== undefined && !item.deleted ? item : undefined
  }

  /** dedupeKey → id（评估套件目标解析：确定性 id 是 k-<hash> 前缀）。 */
  dedupeIds(): Map<string, string> {
    const map = new Map<string, string>()
    if (this.closed) return map
    const rows = this.db.prepare('SELECT dedupe_key, id FROM items WHERE dedupe_key IS NOT NULL').all() as Array<{ dedupe_key: string; id: string }>
    for (const r of rows) map.set(r.dedupe_key, r.id)
    return map
  }

  // ---------- L1 扩展缓存持久化（0.1.5） ----------
  /** 读扩展缓存（按 workspace 隔离；不存在/坏数据 → null）。 */
  getExpansion(wsId: string, normQuery: string): string[] | null {
    if (this.closed) return null
    const row = this.db.prepare('SELECT variants FROM expansion_cache WHERE ws_id = ? AND query = ?')
      .get(wsId, normQuery) as { variants: string } | undefined
    if (row === undefined) return null
    try {
      const v = JSON.parse(row.variants) as unknown
      if (!Array.isArray(v)) return null
      const valid = v.filter((x): x is string => typeof x === 'string' && x.length > 0)
      return valid.length > 0 ? valid : null // 空/全非字符串 = 坏数据，按未命中
    } catch {
      return null // 坏数据按未命中处理，下次扩展覆盖
    }
  }

  /** 写扩展缓存（upsert）。 */
  setExpansion(wsId: string, normQuery: string, variants: string[]): void {
    if (this.closed) return
    this.db.prepare(`
      INSERT INTO expansion_cache (ws_id, query, variants, updated_at) VALUES (?, ?, ?, ?)
      ON CONFLICT(ws_id, query) DO UPDATE SET variants = excluded.variants, updated_at = excluded.updated_at
    `).run(wsId, normQuery, JSON.stringify(variants), Date.now())
  }

  /** 清空扩展缓存（variance/fresh 语义：强制独立扩展）。 */
  clearExpansionCache(): void {
    if (this.closed) return
    this.db.prepare('DELETE FROM expansion_cache').run()
  }

  // ---------- 授权（V1.11 读取面：workspace 本区 + session 属主 + global；写面由调用方打标） ----------
  private canRead(item: StoredItem, caller: KnowledgeStamps & { sessionId: string }): boolean {
    if (item.scope === 'workspace') return item.workspaceId === caller.workspaceId
    if (item.scope === 'session') return item.ownerId === caller.sessionId
    if (item.scope === 'global') return true
    return false
  }

  // ---------- write ----------
  /**
   * 写入/upsert。stamps 由工具层派生（打标字段工具层所有）。
   * @param input 内容与元数据（不得含打标字段）
   * @param stamps 打标：workspaceId/ownerId/authorTier
   * @param allowedGlobalWriters 允许写 global scope 的 actor id 列表（agent/preset id）
   */
  write(
    input: {
      content: string
      scope?: Scope
      source?: { sessionId: string; seq: number } | null
      importance?: number
      tags?: string[]
      dedupeKey?: string
      ttl?: number
    },
    stamps: KnowledgeStamps,
    allowedGlobalWriters: string[],
    actorId: string,
  ): Promise<StoreResult<{ id: string; wasUpdate: boolean; scope: Scope; importance: number }>> {
    if (this.closed) return Promise.resolve(err('closed', 'knowledge store is closing'))
    return this.enqueue(() => {
      const forged = input as unknown as { workspaceId?: unknown; ownerId?: unknown; authorTier?: unknown }
      if (forged.workspaceId !== undefined || forged.ownerId !== undefined || forged.authorTier !== undefined) {
        return err('write-rejected', 'stamp fields (workspaceId/ownerId/authorTier) are tool-layer-owned')
      }
      if (typeof input.content !== 'string' || input.content.trim().length === 0) {
        return err('write-rejected', 'content is required')
      }
      if (estimateTokens(input.content) > this.maxContentTokens) {
        return err('write-rejected', `content exceeds maxContentTokens (${this.maxContentTokens})`)
      }
      const scope: Scope = input.scope ?? 'workspace'
      if (scope !== 'workspace' && scope !== 'session' && scope !== 'global') {
        return err('write-rejected', `invalid scope: ${scope}`)
      }
      if (scope === 'global' && !allowedGlobalWriters.includes(actorId)) {
        return err('write-rejected', 'global scope requires allowedGlobalWriters membership')
      }
      const importance = Math.max(1, Math.min(10, Math.round(input.importance ?? 5)))
      const now = Date.now()
      const dedupeKey = typeof input.dedupeKey === 'string' && input.dedupeKey.length > 0 ? input.dedupeKey : null
      const id = dedupeKey !== null
        ? `k-${djb2(`${stamps.workspaceId}\u0000${scope}\u0000${dedupeKey}`)}`
        : `i-${djb2(`${stamps.workspaceId}\u0000${scope}\u0000${now}\u0000${randomUUID()}`)}`
      const tags = Array.isArray(input.tags) ? input.tags : []
      const ttlSeconds = typeof input.ttl === 'number' ? input.ttl : null
      const source = input.source ?? null

      const existing = this.getItem(id)
      this.db.prepare(`
        INSERT INTO items
          (id, scope, workspace_id, owner_id, author_tier, content, keywords, synonyms, questions,
           content_hash, importance, tags, source, dedupe_key, ttl_seconds, created_at, updated_at, deleted)
        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(workspace_id, scope, dedupe_key) DO UPDATE SET
          id = excluded.id, content = excluded.content,
          content_hash = excluded.content_hash, importance = excluded.importance,
          tags = excluded.tags, source = excluded.source,
          ttl_seconds = excluded.ttl_seconds, updated_at = excluded.updated_at,
          deleted = 0
      `).run(
        id, scope, stamps.workspaceId, stamps.ownerId, stamps.authorTier,
        input.content, djb2(input.content), importance, JSON.stringify(tags),
        source === null ? null : JSON.stringify(source),
        dedupeKey, ttlSeconds, now, now,
      )
      const rowid = (this.db.prepare('SELECT rowid FROM items WHERE id = ?').get(id) as { rowid: number }).rowid
      // FTS 同步：upsert 后 rowid 不变（ON CONFLICT DO UPDATE），OR REPLACE 按 rowid 幂等
      this.db.prepare('INSERT OR REPLACE INTO items_fts_base(rowid, content) VALUES (?, ?)').run(rowid, input.content)
      this.db.prepare('INSERT OR REPLACE INTO items_fts_rich(rowid, content) VALUES (?, ?)').run(rowid, input.content)
      return { id, wasUpdate: existing !== undefined, scope, importance }
    })
  }

  /** 富化写入（trusted writer：enrichment writeback / 评估装载）。保留原打标，仅更新索引字段。 */
  enrich(id: string, fields: { keywords?: string[]; synonyms?: string[]; questions?: string[] }): Promise<StoreResult<{ enriched: boolean }>> {
    if (this.closed) return Promise.resolve(err('closed', 'knowledge store is closing'))
    return this.enqueue(() => {
      const item = this.getItem(id)
      if (item === undefined || item.deleted) return err('missing-key', `unknown id: ${id}`)
      this.db.prepare(`
        UPDATE items SET keywords = ?, synonyms = ?, questions = ?, updated_at = ?
        WHERE id = ?
      `).run(
        fields.keywords?.join(' ') ?? item.keywords,
        fields.synonyms?.join(' ') ?? item.synonyms,
        fields.questions?.join(' ') ?? item.questions,
        Date.now(), id,
      )
      const rowid = (this.db.prepare('SELECT rowid FROM items WHERE id = ?').get(id) as { rowid: number }).rowid
      this.db.prepare('INSERT OR REPLACE INTO items_fts_rich(rowid, content) VALUES (?, ?)')
        .run(rowid, richTextOf({
          content: item.content,
          keywords: fields.keywords?.join(' ') ?? item.keywords,
          synonyms: fields.synonyms?.join(' ') ?? item.synonyms,
          questions: fields.questions?.join(' ') ?? item.questions,
        }))
      return { enriched: true }
    })
  }

  // ---------- update ----------
  update(
    id: string,
    patch: { content?: string; importance?: number; tags?: string[]; ttl?: number | null },
    caller: KnowledgeStamps & { sessionId: string },
  ): Promise<StoreResult<{ updated: boolean }>> {
    if (this.closed) return Promise.resolve(err('closed', 'knowledge store is closing'))
    return this.enqueue(() => {
      const item = this.getItem(id)
      if (item === undefined || item.deleted) return err('missing-key', `unknown id: ${id}`)
      if (!this.canRead(item, caller)) return err('write-rejected', 'caller is not authorized for this item')
      const content = patch.content ?? item.content
      if (patch.content !== undefined) {
        if (typeof patch.content !== 'string' || patch.content.trim().length === 0) {
          return err('write-rejected', 'content must be a non-empty string')
        }
        if (estimateTokens(patch.content) > this.maxContentTokens) {
          return err('write-rejected', `content exceeds maxContentTokens (${this.maxContentTokens})`)
        }
      }
      this.db.prepare(`
        UPDATE items SET
          content = ?, content_hash = ?, importance = ?, tags = ?, ttl_seconds = ?, updated_at = ?
        WHERE id = ?
      `).run(
        content, djb2(content),
        Math.max(1, Math.min(10, Math.round(patch.importance ?? item.importance))),
        JSON.stringify(patch.tags ?? item.tags),
        patch.ttl !== undefined ? patch.ttl : item.ttlSeconds,
        Date.now(), id,
      )
      const rowid = (this.db.prepare('SELECT rowid FROM items WHERE id = ?').get(id) as { rowid: number }).rowid
      this.db.prepare('INSERT OR REPLACE INTO items_fts_base(rowid, content) VALUES (?, ?)').run(rowid, content)
      this.db.prepare('INSERT OR REPLACE INTO items_fts_rich(rowid, content) VALUES (?, ?)')
        .run(rowid, richTextOf({ content, keywords: item.keywords, synonyms: item.synonyms, questions: item.questions }))
      return { updated: true }
    })
  }

  // ---------- search ----------
  /**
   * 检索：topN 个候选（含 score 与 item 字段）。
   * @param texts 查询文本集合（原文 + 扩展变体）
   * @param caller 调用方（读取授权）
   * @param opts scopeFilter / topN / maxQueryTrigrams
   */
  async search(
    table: KnowledgeTable,
    texts: string[],
    caller: KnowledgeStamps & { sessionId: string },
    opts: { scope?: 'workspace' | 'session' | 'global' | 'all'; topN?: number; maxQueryTrigrams?: number } = {},
  ): Promise<Array<{ item: StoredItem; score: number }>> {
    if (this.closed) return []
    const topN = Math.max(1, Math.min(opts.topN ?? 20, 200))
    const fts = table === 'rich' ? 'items_fts_rich' : 'items_fts_base'
    const grams = new Set<string>()
    for (const t of texts) for (const g of queryGrams(t)) grams.add(g)
    if (grams.size === 0) return []
    // 生产封顶：idf 优先截断（dfOf 从 fts5vocab 读取；不可用时回退顺序截断——cap 默认 0）
    let qgrams = [...grams]
    const cap = opts.maxQueryTrigrams ?? 0
    if (cap > 0) {
      const dfOf = this.dfOf(fts)
      qgrams = truncateGrams(qgrams, dfOf, this.docCount(fts), cap)
    }
    const now = Date.now()
    const scopeSql = opts.scope === undefined || opts.scope === 'all'
      ? ''
      : ' AND i.scope = ?'
    const params: Array<string | number> = [
      matchOf(qgrams), now, caller.workspaceId, caller.sessionId,
    ]
    if (scopeSql !== '') params.push(opts.scope as string)
    params.push(topN)
    const sql = `
      SELECT f.rowid, bm25(${fts}) AS score
      FROM ${fts} f JOIN items i ON i.rowid = f.rowid
      WHERE f.${fts} MATCH ?
        AND i.deleted = 0
        AND (i.ttl_seconds IS NULL OR i.created_at + i.ttl_seconds * 1000 > ?)
        AND (
          (i.scope = 'workspace' AND i.workspace_id = ?)
          OR (i.scope = 'session' AND i.owner_id = ?)
          OR (i.scope = 'global')
        )
        ${scopeSql}
      ORDER BY score LIMIT ?
    `
    try {
      const rows = this.db.prepare(sql).all(...params) as Array<{ rowid: number; score: number }>
      return rows.map((r) => {
        const item = this.getItemByIdRow(r.rowid)
        return { item, score: r.score }
      })
    } catch {
      return []
    }
  }

  private getItemByIdRow(rowid: number): StoredItem {
    const row = this.db.prepare('SELECT * FROM items WHERE rowid = ?').get(rowid) as Record<string, unknown>
    return this.rowToItem(row)
  }

  /** 文档频率（cap>0 的 idf 截断用）：扫描 FTS 表内容统计（O(N)，cap 默认 0 不触发）。 */
  private dfOf(fts: string): Map<string, number> {
    const map = new Map<string, number>()
    try {
      const rows = this.db.prepare(`SELECT content FROM ${fts}`).all() as Array<{ content: string }>
      for (const r of rows) {
        for (const g of new Set(docGrams(r.content))) map.set(g, (map.get(g) ?? 0) + 1)
      }
    } catch {
      // 空表或不可用 → 空 map，truncateGrams 退化为顺序截断
    }
    return map
  }

  private docCount(fts: string): number {
    try {
      const row = this.db.prepare(`SELECT count(*) AS c FROM ${fts}`).get() as { c: number }
      return Number(row.c)
    } catch {
      return 0
    }
  }

  // ---------- list ----------
  list(
    scopeFilter: 'workspace' | 'session' | 'global' | 'all',
    opts: { cursor?: string; limit?: number; includeDeleted?: boolean; includeExpired?: boolean },
    caller: KnowledgeStamps & { sessionId: string },
  ): KnowledgeListResult {
    if (this.closed) return { items: [] }
    const limit = Math.max(1, Math.min(opts.limit ?? 50, 200))
    const offset = typeof opts.cursor === 'string' && /^\d+$/.test(opts.cursor) ? Number(opts.cursor) : 0
    const now = Date.now()
    const where: string[] = []
    const params: Array<string | number> = []
    if (opts.includeDeleted !== true) where.push('i.deleted = 0')
    if (opts.includeExpired !== true) {
      where.push('(i.ttl_seconds IS NULL OR i.created_at + i.ttl_seconds * 1000 > ?)')
      params.push(now)
    }
    where.push(`(
      (i.scope = 'workspace' AND i.workspace_id = ?)
      OR (i.scope = 'session' AND i.owner_id = ?)
      OR (i.scope = 'global')
    )`)
    params.push(caller.workspaceId, caller.sessionId)
    if (scopeFilter !== 'all') {
      where.push('i.scope = ?')
      params.push(scopeFilter)
    }
    params.push(limit + 1, offset)
    const sql = `
      SELECT i.* FROM items i
      WHERE ${where.join(' AND ')}
      ORDER BY i.created_at DESC
      LIMIT ? OFFSET ?
    `
    const rows = this.db.prepare(sql).all(...params) as Array<Record<string, unknown>>
    const items: KnowledgeMeta[] = rows.slice(0, limit).map((row) => {
      const item = this.rowToItem(row)
      return {
        id: item.id,
        content: item.content,
        scope: item.scope,
        authorTier: item.authorTier,
        importance: item.importance,
        dedupeKey: item.dedupeKey,
        ttlSeconds: item.ttlSeconds,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        expired: item.ttlSeconds !== null && item.createdAt + item.ttlSeconds * 1000 <= now,
        deleted: item.deleted,
      }
    })
    const nextCursor = rows.length > limit ? String(offset + limit) : undefined
    return { items, nextCursor }
  }

  // ---------- delete ----------
  delete(id: string, caller: KnowledgeStamps & { sessionId: string }): Promise<StoreResult<{ deleted: boolean }>> {
    if (this.closed) return Promise.resolve(err('closed', 'knowledge store is closing'))
    return this.enqueue(() => {
      const item = this.getItem(id)
      if (item === undefined) return err('missing-key', `unknown id: ${id}`)
      if (!this.canRead(item, caller)) return err('write-rejected', 'caller is not authorized for this item')
      if (item.ttlSeconds !== null && item.createdAt + item.ttlSeconds * 1000 <= Date.now()) {
        return { deleted: false } // 过期条目 delete → false（V1.11）
      }
      this.db.prepare('UPDATE items SET deleted = 1, updated_at = ? WHERE id = ?').run(Date.now(), id)
      return { deleted: true }
    })
  }
}
