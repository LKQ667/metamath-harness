# Memory Knowledge Seam (`ctx.knowledge`) — 社区设计文档（V1.11）

> **来源说明**：本文为社区设计提案全文（评审收敛版 V1.11），原载于
> DeepSeek Harness 仓库 `.agents/notes/proposed/feature/`（本地未提交）。
> **非官方设计**——由社区评审链（11 轮，0 Critical / 0 Major / 0 Minor）收敛。
> 实现：dsh-knowledge-sqlite（本仓库）。评审链摘要见 [REVIEWS](REVIEWS.md)，
> 实验证据见 [EXPERIMENTS](EXPERIMENTS.md)。

Status: proposed
Version: 1.11

English | [中文](2026-08-14-memory-knowledge-seam.zh.md)（原文档位于兄弟工作区 research/memory-knowledge-seam/proposal/，不在本仓库）

**Revision log**: V1.0 initial proposal · V1.1 full spec (contracts, data flows, alternatives, AC, test matrix) · V1.2 architecture-review + red-team fixes (metric correction 7/29/36/64, config reorder, control arms, authorization, update/dedupeKey, TTL, cascade) · V1.3 adjudication clarifications (ownership stamping, model fallback, tokenMeter naming, PRF qualification, tool-path truncation) · V1.4 red-blue round (trust model + authorTier, three-layer authorization, tombstones, pagination, idempotency claims, scale budgets) · V1.5 v4-pro final adjudication fixes (enrichment idempotency restored, AC mean±range semantics, p95 2.0s < timeoutMs 2.5s, contract stamp fields, retrieval schema budgets, scale/human-set gate data from RESULTS-v3) · V1.6 v1.5-adjudication fixes (human-set L1 corrected to 82%, stamp fields tool-layer-owned + spoofing rejection, update-path authorization + phase-1 scope/dedupeKey immutability, human-set precision@1 ≥ 80% gate, PRF fallback path + rank-3 inversion, retrieval schema block re-added, oversized-item drop rule, human-set L1 gate, risk rewrite, RESULTS-v3 MRR reconciled) · V1.7 v1.6-adjudication minors (trusted internal writers for stamp tiers; precision@1 informational on single-target suites + precision@5 ≥ 0.3 binding once measured; matrix test rows for stamp rejection / update scope-immutability / update→global re-check; human-set C/D arms join the variance clause; zh mirror: dedup fixes + retrieval schema `topN` + human-set L1 82%). · V1.8 v1.7-adjudication minors (writer-registration semantics as a phase-2 precondition; human-set variance floors mean-based + provisional per-run floors; protocol adjudication chain added to References) · V1.9 v1.8-adjudication minors (V1.8 revision-log entry added; zh References protocol-chain mirror added). · V1.10 v1.9-adjudication minors (References protocol chain switched to directory citation, reducing the self-referential per-round chain; zh trailing double-period removed) · V1.11 v1.10-adjudication minors (References citation reduced to pure directory reference — no version enumeration; zh duplicated closing phrase removed).

## Problem

Cross-session knowledge is the one capability the harness lacks at the engine level. Every durable mechanism that exists today stops short of retrieval:

- The session log (`sessionPersistence`) is the only "memory stream", but it is append-only history, not searchable knowledge (full-text search is opt-in and covers sessions, not knowledge items).
- `storageDomain` provides typed durable KV with a write chain and change events, but has **no query/retrieval facet** — the KV note itself lists "secondary indexes / conditional queries" as future work.
- The always-on tier (skills catalog, `systemPrompt` dynamic sections, preset personas) is the equivalent of CLAUDE.md-style standing context, but is human-authored static guidance.
- No model-facing tool can write a fact once and retrieve it across sessions.

A benchmark of the industry (Claude Code, Cursor, Windsurf, Cline/Roo memory banks, Mem0, Letta/MemGPT, Zep, LangGraph Store, Aider) yields three cross-cutting findings:

1. **File-based memory dies on the triple problem**: full injection, no retrieval, context bloat — CLAUDE.md truncation (#5128), memory-bank whole-file reads, and "context rot" are all symptoms of the same missing retrieval layer.
2. **Trust spectrum**: human-curated explicit writes are trusted; deterministic programmatic folds (Aider repo map) are trusted; LLM auto-captured memories (Windsurf, Cursor Memories, Claude auto-memory) are mistrusted — wrong content, hard to audit, hard to clear.
3. **Rules ≠ searchable memory**: declarative rules injected by glob and indexed knowledge retrieved on demand are different mechanisms; the industry separates them, and the missing piece in every file-based design is the retrieval half.

> **Evidence-strength note** (red-team finding): finding 1 rests on documented sources; finding 2 rests largely on community reports (Windsurf failure write-ups, Cursor forum threads) — community-grade, and Cursor "Memories" is absent from official docs; finding 3 rests on documented product behavior. Treat trust claims as directionally sound, not settled.

## Proposal

Add **`ctx.knowledge`**, a capability seam in the established three-way split (interface package / implementation packages / model-facing tool package), following the `ctx.web` precedent: the engine owns the contract, plugins own the storage form and retrieval algorithm.

### Package structure

| Package | Role |
|---|---|
| `dsh-knowledge` | Seam: service definition, schemas, error semantics, events. No storage, no algorithm. |
| `dsh-knowledge-sqlite` | Default implementation: FTS5 (trigram) index + optional enrichment fields + async enrichment queue. |
| `dsh-tool-knowledge` | Model-facing tools: `knowledge_write` / `knowledge_search` / `knowledge_delete` / `knowledge_list`. |
| (future) `dsh-knowledge-files` | Markdown-file backend (CLAUDE.md-compatible project memory). |
| (future) `dsh-knowledge-dense` | Local-embedding provider (transformers.js/fastembed, ONNX, BGE-small class) — level 3. |

### Seam contract

```ts
// Write: providers own how and where items are stored. Durability before memory, like storageDomain.
knowledge.write(item: KnowledgeItemInput): Promise<{ id: string }>
// Correction path: replace content/fields of an existing item, preserving id, provenance, enrichment.
knowledge.update(id: string, item: Partial<KnowledgeItemInput>): Promise<boolean>
// Query: the budget is the contract, not the result shape.
knowledge.search(query: string, opts?: SearchOptions): Promise<KnowledgeHit[]>
// Auditability: every item is listable and removable; cursor-paged.
knowledge.list(scope?: ScopeFilter, path?: string, opts?: ListOptions): Promise<{ items: KnowledgeMeta[]; nextCursor?: string }>
knowledge.delete(id: string): Promise<boolean>

interface KnowledgeItemInput {
  content: string                                  // maxContentTokens enforced at write (write-rejected when over)
  scope: 'workspace' | 'session' | 'global'        // global is opt-in, see authorization below
  workspaceId?: string                             // stamped by the tool layer (canonical); seam validates against caller
  ownerId?: string                                 // stamped by the tool layer (writing session id)
  authorTier?: 'human' | 'explicit' | 'derived' | 'llm'  // stamped by the tool layer; 'explicit' default
  source?: { sessionId: string; seq: number }  // provenance; links back into the session log
  importance?: number                          // 1-10, default 5
  tags?: string[]
  dedupeKey?: string                               // upsert key; uniqueness is (workspace, scope, dedupeKey)
  ttl?: number                                     // seconds
}
interface SearchOptions {
  scope?: 'workspace' | 'session' | 'global' | 'all'
  path?: string
  budget?: { maxTokens: number; maxItems: number }
  expand?: boolean                                 // L1 query expansion; default true on the model-tool path, false on injection
  variants?: string[]                              // caller-supplied expanded phrasings (skips the expansion call)
  signal?: AbortSignal
}
interface ListOptions {
  cursor?: string
  limit?: number                                   // default 50
  includeDeleted?: boolean
  includeExpired?: boolean
}
interface KnowledgeHit {
  id: string; content: string; score: number; snippet: string
  provenance?: 'original' | 'enriched'   // which field the snippet's match window came from
  authorTier?: 'human' | 'explicit' | 'derived' | 'llm'  // trust tier of the item (see trust model)
}
```

**Item identity**: id is deterministic when `dedupeKey` is present (`hash(workspace + scope + dedupeKey)`); otherwise provider-generated. Upserts never change the id, so provenance links survive.

**Write ordering**: `write`/`update`/`delete` serialize on one provider-owned write chain (the `storageDomain` chain when bodies go through it, otherwise a provider-internal chain), so `update` and dedup resolve deterministically under concurrent writers. Search reads take a consistent snapshot per query (provider-level transaction or copy-on-read).

**Ownership and identity stamping**: the tool layer stamps every `write`/`update` before the seam call with: `workspaceId` (**canonicalized** — resolved from the caller's cwd via realpath/workspace-registry identity, never raw cwd-string equality; symlink/`..`/`~` spellings of the same directory resolve to the same id), `ownerId` (the writing session's id), and `authorTier` (`explicit` for model-tool writes, `derived` for fold writes, `llm` for extraction writes, `human` reserved for the phase-2 write surface). Callers with no resolvable workspace are rejected, as `tool-session-query` rejects undefined cwd. Actor ids in `allowedGlobalWriters` are **agent/preset ids** (stable across session recreation), not session ids.

**Stamp fields are tool-layer-owned**: `workspaceId`/`ownerId`/`authorTier` are never trusted from caller input — caller-supplied values are rejected with `write-rejected` (providers may defensively overwrite instead of reject); the model-facing `knowledge_write` schema does not expose them; `authorTier: 'human'` is set exclusively by the phase-2 human surface or the files backend. **Trusted internal writers**: the fold bridge (→ `derived`), enrichment writeback (→ preserves original stamps), and the files backend (→ `human`) are registered writers allowed to set their tiers; a defensive overwrite uses the provider's own caller-resolved truth (canonical workspace id, caller session, tier per writer class). Test: caller-supplied stamp values are rejected. **Registration semantics (phase-2 precondition)**: writer classes are registered in provider config; only harness-shipped classes may set their tiers, and only the phase-2 human surface / official files backend may set `human`.

**TTL semantics**: expired items are filtered from `search` results at query time; `list()` shows them flagged `expired: true` (so users can see why something vanished); `delete()` of an expired item returns `false`.

**Error semantics** (mirroring `DomainError` style): `closed` (provider closing), `missing-key` (delete/update of unknown id), `write-rejected` (provider refused, e.g. global scope without authorization). Provider-local failures never surface raw.

**Events** (unfiltered, notification-only, like `domain/changed`; payload carries the location so consumers can invalidate without lookup): `knowledge/written { id, scope, importance }`, `knowledge/updated { id, scope }`, `knowledge/deleted { id, scope }`. Enrichment completion emits `knowledge/written` again with the same id and a `enriched: true` flag.

**Config schema** (dsh-knowledge, seam defaults; per-provider config lives in the provider row):

```ts
z.object({
  defaultScope: z.enum(['workspace', 'session']).default('workspace'),
  queryExpansion: z.object({               // default-on retrieval stage (model-tool path)
    enabled: z.boolean().default(true),
    model: z.string().optional(),            // unset = session model (never degrades silently to L0)
    maxOutputTokens: z.number().default(300),
    timeoutMs: z.number().default(2500),     // on timeout/error: lexical fallback with degraded: 'lexical' flag, not a tool error
    cache: z.boolean().default(true),        // cache expanded variants per normalized query
  }),
  enrichment: z.object({                   // opt-in write-side enhancement
    enabled: z.boolean().default(false),
    model: z.string().optional(),            // unset = session model (same fallback as queryExpansion)
    batchWindowMs: z.number().default(5000),
    maxOutputTokens: z.number().default(200),
    importanceThreshold: z.number().default(6),
    idleOnly: z.boolean().default(true),
    maxContentTokens: z.number().default(2048), // seam-level write cap: applies whether or not enrichment is enabled (oversized: write-rejected; enrichment additionally skips with 'skipped-oversize')
  }),
  injection: z.object({
    enabled: z.boolean().default(false),   // Windsurf lesson: default off
    maxTokens: z.number().default(800),
    maxItems: z.number().default(3),
  }),
  retrieval: z.object({                       // scale budgets (prose in the search flow)
    topN: z.number().default(20),
    maxQueryTrigrams: z.number().default(24),
    maxCandidates: z.number().default(200),
  }),
  authorization: z.object({
    allowedGlobalWriters: z.array(z.string()).default([]), // agent/preset ids allowed to write global scope
  }),
})
```

### Retrieval design (revised after review)

The experiment (below) measured across three query sets and two corpus sizes (true recall@1): (a) 14 deliberately-rewritten LLM queries (zero lexical overlap) on 12 items — pure lexical 7%, write-enrichment-only 29%, query-expansion-only 36%, both 64%; (b) the same queries on 512 items (12 memories + 500 real doc paragraphs) — 7%/21%/21%/50%, precision@5 0.143; (c) **20 real human messages extracted from actual session logs** on 522 items — lexical 65%, expansion 82% (14/17), both 88%. Two consequences for the design:

1. **Query-time expansion alone beats write-time enrichment alone** (36% vs 29%, and it requires zero write-side machinery). The default therefore becomes: **pure lexical retrieval + on-demand query expansion** (one small LLM call per search on the model-tool path; injection path never expands). Write-time enrichment is demoted to an **opt-in enhancement** (measured marginal gain +28pp when both run: 64−36), batched idle-only, enabled where recall matters more than tokens.
2. **Deterministic expansion is not a substitute at recall@1, but the scale flip is partial**: pseudo-relevance feedback measured 7% recall@1 (identical to baseline) at 12 items, and 7% recall@1 / 36% recall@3 at 512 items — at rank 3, PRF (36%) already beats expansion (29%) at 512 items; rank 1 remains the gap. The cost-minimization claim "term tables / PRF replace LLM expansion" stays withdrawn. The PRF fallback is a **model-tool-path candidate** when LLM expansion is unavailable; the injection path stays pure lexical in phase 1 (PRF for injection is a possible phase-2 deterministic upgrade).

| Stage | Mechanism | Query-time cost | Measured recall@1 (hard set / 512 items / human) |
|---|---|---|---|
| L0 | Pure lexical FTS (trigram) | zero | 7% / 7% / 65% |
| **L1 (default)** | **+ query-time expansion** (model-tool path only) | 1 small call/search | 36% / 21% / 82% |
| L2 (opt-in) | + write-time enrichment (idle-batched, piggyback when free) | zero at query time (rerank, if used, costs like L1) | 64% / 50% / 88% (with L1) |
| L3 (upgrade) | + local dense (transformers.js/fastembed) | local inference | unmeasured |
| L4 (upgrade) | + external embedding provider | API call | unmeasured |

The relevance-provider contract is unchanged across levels; upper layers never change. **Cost is per-mode explicit**: L1 pays per search on the model-tool path (the primary consumption mode) — one small call, cached per normalized query, hard-timeout with lexical fallback (`degraded: 'lexical'` metadata, never a tool error), skippable via `expand: false` or caller-supplied `variants`; enrichment pays only when enabled and only at write time (batched/idle). When the enrichment queue is starved (`idleOnly` + busy machine) or disabled, quality is exactly the measured 36% level — deterministic, not silently degraded. **The injection path runs at L0 lexical quality by design** (never LLM stages, never expansion): the "default quality" claim applies to the model-tool path only, and presets that enable injection inherit L0 — documented, not implied. The optional listwise rerank is a **query-time LLM call** and therefore belongs to L1's cost envelope, not L2's "zero at query time".

### Data flow: write lifecycle

1. `write` lands the item **synchronously with the lexical index** — immediately searchable, zero LLM.
2. Enrichment (if enabled): piggyback when the deciding generation carries the fields; otherwise idle-batched queue, cheapest route, `maxOutputTokens` capped; failure → log + retry window, final failure leaves the item lexical-only. **Crash durability**: queue entries are persisted (storageDomain row or provider table) and re-queued on startup, so a crash mid-queue does not silently drop enrichment.
3. Enrichment writes back only index fields; `content` is never rewritten. **Idempotency guard**: every write/update stamps `contentHash`; an enrichment completion carries `baseContentHash` and the provider ignores it when `baseContentHash !== current.contentHash` (a concurrent content update during in-flight enrichment never lands stale terms); a content update marks the item `needsEnrichment`; writeback upserts by `{id, baseContentHash}` so repeated completion for the same hash fires `knowledge/written {enriched: true}` exactly once. `knowledge/written` fires on land, re-fires with `enriched: true` on completion.

### Data flow: search

1. Normalize query → provider lexicons.
2. Provider retrieves top-N (default 20) by its own ranking — trigram OR + BM25 over content (+ enrichment fields when present). (Experiment depth is top-5; recall@1 is depth-independent, while precision@5/NDCG@5 report the 5-window — a stricter window than the design's 20.)
3. L1 stage (model-tool path only, `expand !== false`, no cached/caller variants): one query-expansion call under `timeoutMs`; on timeout/error fall back to provider top-k with `degraded: 'lexical'`; merged gram set, re-rank; optional LLM listwise rerank of top-20→k counts as a query-time cost. Expansion results are cached per normalized query. Query gram count is capped (`maxQueryTrigrams`, default 24) and candidate sets are capped before ranking (`maxCandidates`, default 200) to bound latency at scale.
4. Budget truncation: `budget.maxItems` by the provider; **`budget.maxTokens` is enforced by the injection consumer using `ctx.tokenMeter`'s estimation function (`dsh-token-meter`)** (providers do not own a tokenizer). On the model-tool path without a `budget`, results are truncated by the tool layer using the same estimator plus the existing spill policy for oversized tool results. The `system-prompt/assemble` waterfall does NOT arbitrate budgets today — the arbitration point is the injection consumer itself.
5. Injection path never exceeds budget and never performs LLM stages.

### The three consumption modes (revised)

1. **Model tool** (`tool-knowledge`) — the primary path; stable names `knowledge_*`, dual-registered (`knowledge_search` + `tool:knowledge_search`) like `tool-web`'s `web_search`. `knowledge_write` and `knowledge_delete` register through the tools approval seam (`ask`-gated by default, overridable per permission preset) — knowledge mutation is a consent surface like bash writes, not silent. Both aliases resolve through the same policy (no bypass via the alternate name).
2. **Auto-injection** — a push-updated cache: a subscriber maintains a small per-session candidate set; the `systemPrompt.context()` provider (synchronous, as the engine requires today) reads the cache. Freshness = last cache update, not per-assembly; the cache refreshes on session events (user message, tool result). Default off. Cache entries carry `{ itemId, scope, workspaceId, ownerId, authorTier }`; a single item whose estimated tokens exceed the injection budget is **dropped from the candidate set, never truncated** (truncation corrupts factual content); the drop count surfaces in settings counters; the provider filters at read time through the same `authorize()` used by `knowledge_search`, and **only `authorTier: 'explicit' | 'human'` items are injected** — `derived`/`llm` content never enters context unflagged. Injected content carries a provenance prefix so the model can tell memory from instruction. (Async context providers would be a small engine change; not required by this design.)
3. **Derived capture** — deterministic fold, with an explicit bridge: a `sessionProjections` unit folds metadata-only state (id, scope, importance, content hash); a **separate consumer subscribes to the projection change feed** and writes item bodies into the provider store. Cold-start: after `restore()` replays the log without driving the feed, a **reconciliation pass** re-emits view output once per session so the store converges. **Tombstones**: a user's `knowledge.delete` records a tombstone the fold bridge checks before every write and the reconciliation pass checks before every re-emit — deleted fold items never resurrect. LLM extraction is an opt-in provider whose output is auditable like explicit writes.

### Authorization (new)

Three layers, mirroring the codebase's existing isolation surfaces:

1. **Workspace layer** (mirror of `tool-session-query`'s `workspaceAccess`, with identity fixed): authorize by the **canonical workspace id** (realpath/registry identity), never raw cwd-string equality — symlink/`..`/`~` spellings of one directory are one pool, and undefined-cwd callers are rejected. `workspace` scope: read/write/delete only within the caller's workspace; `path` filter subdivides it.
2. **Preset/scope layer** (mirror of `ctx.skills`' `ScopedLayers`): knowledge tool rows register per agent-preset scope chain, so a sandbox-restricted subagent preset can be composed without `knowledge_*` tools at all, and one preset's contributions layer like skills do. Cross-preset reads default to denied at the tool-registration level, not just authorization time.
3. **Approval layer**: `knowledge_write`/`knowledge_delete` are `ask`-gated through the tools approval seam (consent for durable cross-session mutation, like bash writes); `global` scope additionally requires `allowedGlobalWriters` membership (agent/preset ids, stable across session recreation). Headless deployments without a configured writer are denied global writes with `write-rejected` — config gating replaces interactive confirmation.
4. `session` scope is **scratch memory**: readable/writable only by the owning session; on session end (close/fork/restart), items are tombstoned after one retention window and purge — no silent orphan accumulation. Its purpose is transient working notes; durable knowledge belongs to `workspace` scope. (`session` scope may be dropped entirely in phase 1 if it adds no measured value; `storageDomain` already covers session-local durable state.)
5. **Update-path authorization**: `update` applies the same authorization as `write` for the target state; an update that changes `scope` to a broader tier re-runs the target tier's checks (workspace→global requires `allowedGlobalWriters` membership, else `write-rejected`). In phase 1, `scope` and `dedupeKey` are **immutable after write**: mutation attempts are `write-rejected`, preserving id determinism (`hash(workspace+scope+dedupeKey)`). Test rows for both.
6. The seam exposes `authorize(actor, action, item)`; the tool layer is the enforcement point, and the injection provider applies the same function at read time. Providers may also enforce defensively. Cross-workspace `shared` scope / ACLs are explicitly out of scope for phase 1 (finding B3): a workspace B call for an item stamped workspace A receives `not-found` or `write-rejected`, never content.

### Workspace lifecycle

The knowledge provider subscribes to workspace deletion (a hook/event to be added alongside `workspaceRegistry.delete`, which today is metadata-only) and cascades: `workspace`-scope items are tombstoned (hidden from `search`, shown in `list` as `deleted: true` for one retention window, then purged).

### Enrichment field taxonomy (trust boundary)

- **Lexical fields** (`keywords`, `synonyms`): word-level index terms; low factual risk.
- **Assertive fields** (`questions`): LLM-generated phrasings that can carry factual claims (a hallucinated question could rank an item first with a false claim in the snippet). Hits whose snippet window comes from an assertive field carry `provenance: 'enriched'` so consumers (and future UI) can show the distinction; original content is always available on the item.

### Trust model (red-blue finding F1)

Every write path today is model-authored; without an author tier, model-read content (including attacker-controlled README text) can be laundered into durable items re-injected into future sessions — a cross-session prompt-injection amplifier. Defenses:

1. **`authorTier` on every item** (`human` | `explicit` | `derived` | `llm`), stamped at write and enforced at read: injection accepts only `human`/`explicit`; `derived`/`llm` items are searchable via the tool (with `provenance` flags) but never enter context unflagged.
2. **A human write surface is a phase-2 commitment, not absent**: the out-of-scope note below is revised accordingly; phase 1 ships `list`/`delete` tools plus settings counters, and the human write path (a minimal "review/edit memories" panel) is explicitly sequenced as phase 2 — until then, `human`-tier items are written via files (the `dsh-knowledge-files` backend reads human-authored markdown).
3. Injection provenance prefix so the model can distinguish recalled memory from standing instructions.

### Out-of-scope list

- A default semantic provider (local dense is an optional upgrade, not first phase).
- Auto-capture **enabled by default** (trust spectrum; folds are deterministic, LLM extraction opt-in).
- Cross-device sync / cloud knowledge store.
- Knowledge-graph default implementation (Zep-style; entity extraction is a possible future provider).
- Cross-workspace `shared` scope / ACLs (phase 1; `global` is not a substitute).
- Dedicated knowledge management UI (phase 1: settings panel with counters + kill switch only; **phase 2 commitment: a minimal human review/write panel is what makes the `human` author tier real**).

## Alternatives considered

1. **Pure FTS, no stages** — recall@1 7% on the hard set; rejected (experiment).
2. **Write-time enrichment as the default stage** — measured 29%, below query-expansion-only 36% at higher machinery cost; demoted to opt-in L2 (red-team finding).
3. **Deterministic expansion (term tables / PRF) as the LLM-free substitute** — measured 7% recall@1 (PRF, small corpus; recall@3 14% vs 7%, within noise); withdrawn as a rank-1 claim; measured at 512 items: 7% recall@1 / 36% recall@3 — a real rank-3 gain at scale, still no rank-1 substitute; retained as a candidate L1 fallback when LLM expansion is unavailable.
4. **Vector retrieval as the default** — requires an embedding endpoint DeepSeek does not provide; kept as upgrade L3/L4.
5. **CLAUDE.md-style full injection** — the triple problem; rejected.
6. **LLM auto-capture on by default (Windsurf-style)** — mistrusted; rejected as default.
7. **Expose storageDomain tables directly to the model** — no retrieval face; rejected.
8. **`global` scope on by default** — cross-project leakage (#25947); opt-in with config-gated writers.
9. **One monolithic memory plugin** — violates "engine owns mechanisms, plugins own forms"; rejected.

## Acceptance criteria

- [ ] L1 (default) recall@1 ≥ 30% **by 10-run mean** on the hard rewritten-query suite (measured 35.7%, range 29–43%), with no run below 20%; L1+L2 ≥ 60% by 10-run mean (measured 63.6%, range 50–79%), with no run below 45%. Gate semantics: mean-based, per-run floor as stated.
- [ ] The evaluation suite (scripts + datasets) is checked into the repo so the gate is reproducible — including the cross-model query set.
- [ ] Independent query sets: cross-model (done: reasoner, 12 queries) and **human-written (done: 20 real user messages from actual session logs, LLM-labeled, user-verified with 2 user corrections)** — both required before implement-branch promotion.
- [ ] Variance: ≥ 10 runs reported with mean±range for **both the C arm (backs the default-config gate)** and the D arm (done: C 35.7% [29–43], D 63.6% [50–79]); **human-set C/D arms join the 10-run variance clause** (single-run values are advisory; current human-set margins are wide: 82 vs 50, 88 vs 60). The human-set gates are **mean-based**; per-run floors are set once the first 10 human-set runs exist (provisional: L1 ≥ 40%, L1+L2 ≥ 50% per run, calibrated on the data).
- [ ] A written item is searchable **immediately** by lexical query with zero LLM involvement.
- [ ] Enrichment failure never blocks the write; crash mid-queue re-queues on startup; final failure leaves the item lexical-only.
- [ ] Every item is listable and deletable (auditability); deletion emits `knowledge/deleted` with scope.
- [ ] Authorization: cross-workspace `knowledge_search/list/delete` are denied; `global` writes require `allowedGlobalWriters` membership; headless denial is explicit (`write-rejected`).
- [ ] Workspace deletion tombstones its workspace-scope items.
- [ ] Works headless / via SDK with no UI dependency (global writes config-gated, not UI-confirmed).
- [ ] Injection is off by default; when on, it never exceeds `budget` (enforced via `ctx.tokenMeter` estimation), never performs LLM stages, filters through `authorize()`, and injects only `human`/`explicit`-tier items.
- [ ] Human-query-set quality gate: **L1 ≥ 50% and L1+L2 ≥ 60%** recall@1 on the human set (measured 82% / 88%, 522-item corpus).
- [ ] Scale gate: recall and precision measured at ≥ 500 items with real distractor paragraphs (done: 512 items; D arm 50% recall@1 / precision@5 0.143 on the hard set — a stress diagnostic for adversarial zero-overlap queries, not the user-facing contract).
- [ ] **Human-set precision gate: precision@1 ≥ 80% (measured 88%)** — informational on single-target query suites (precision@1 equals recall@1 there); once human-set precision@5 is measured (promotion requirement), a precision@5 threshold (provisional ≥ 0.3, calibrated on the data) binds to this gate. Human-set NDCG@5 must also be reported. The research plan's provisional precision@5 ≥ 0.4 is recorded as superseded: hard-set precision@5 (0.143) measures adversarial rewrites as a stress diagnostic, not the user-facing retrieval contract.
- [ ] P95 L1 search latency ≤ 2.0s on the human query suite under 4-way concurrent load; `degraded: 'lexical'` fallback queries are excluded from p95 (they are not full L1 searches); the expansion `timeoutMs` default 2.5s leaves headroom above the SLO.
- [ ] `knowledge_write`/`knowledge_delete` are `ask`-gated by default and both tool aliases resolve through one policy.
- [ ] `dedupeKey` uniqueness is scoped to `(workspace, scope, dedupeKey)`; a cross-workspace same-key write cannot affect another workspace (tested).
- [ ] Deleted fold items never resurrect: tombstones are honored by the fold bridge and the reconciliation pass (tested).
- [ ] Enrichment idempotency: a stale completion (baseContentHash mismatch) never lands; repeated completion for the same hash fires `knowledge/written {enriched:true}` exactly once (fault-injection tested).
- [ ] `list` pagination: listing 5,000 items produces paged results with stable cursors, no oversized tool result.
- [ ] Seam, authorization, and provider tests run in the harness vitest suites with mocked expansion (LLM evals are an optional benchmark, not a CI gate).

## Test matrix

| Area | Tests |
|---|---|
| Seam contract (vitest) | write/update/search/list/delete round-trip per backend; dedupeKey upsert scoped (workspace, scope, dedupeKey); deterministic id; error semantics; event payloads (scope on all three) |
| sqlite provider | FTS5 trigram OR ranking; enrichment fields join; CJK substring; 2-char term limitation (known); ttl semantics (filter/list-flag/delete-false) |
| Enrichment queue | batching, idleOnly, failure→retry→lexical fallback, crash re-queue, piggyback, importance routing, **contentHash stale-write-back guard (fault-injection: concurrent update during in-flight enrichment)** |
| Tools + authorization | schema validation; budget truncation; abort; cross-workspace denial; global writer allowlist; headless denial; approval `ask` gating; alias policy identity; canonical workspace id (symlink/../~ spellings); undefined-cwd rejection; preset-scope tool layering; **caller-supplied stamp rejection; update scope-immutability write-rejected; update→global allowedGlobalWriters re-check** |
| Pagination + limits | cursor stability; default limit 50; includeDeleted/includeExpired; maxContentTokens write-rejected; oversized-enrichment skip |
| Injection | default off; budget enforced with ctx.tokenMeter estimator; no LLM stages; cache freshness documented; authorize() filter at read; only human/explicit tiers injected; provenance prefix |
| Fold unit + bridge | deterministic replay; metadata-only state; change-feed consumer writes bodies; cold-restore reconciliation converges; tombstone honored by bridge and reconciliation (no resurrection) |
| Workspace lifecycle | deletion tombstones workspace items; retention purge |
| Evaluation suite | `eval.mjs` + `eval-cross.mjs` run in CI; 10-run variance gate |

## Risks

- **CJK 2-character terms** are structurally below the trigram 3-char floor (measured on the hard set). Mitigations: bigram mixing, lexicon tokenization, longer generated variants — but pure trigram has a ceiling; the acceptance suite keeps this documented rather than hidden.
- **Evaluation bias**: the hard and reasoner sets are LLM-written; the human set (done, user-verified) is extracted from the design session itself — instruction-natured queries with heavy lexical overlap (lexical baseline 65% vs 7% hard set), so it measures natural-message retrieval, not adversarial rewrite robustness. A second, session-external human sweep remains a promotion-plus goal. The cross-model set (100% on reasoner queries) was built without the zero-overlap rule, measuring query naturalness as well as model independence.
- **Precision at scale**: measured at 512 items — precision@1 equals recall@1 (50% hard set / 88% human set), precision@5 0.143 on the hard set (real doc paragraphs partially match queries and enter top-5). False-positive ranking at 1000+ items remains untested; the scale corpus gate is executed, not waived.
- **Injection cache staleness**: push-updated injection can serve stale candidates; freshness is documented (per session events), not per assembly.
- **Dual-write consistency**: derived folds never overwrite explicit content (fold writes are `dedupeKey`-scoped and lower priority than explicit writes).
- **Enrichment quality drift**: generated questions age as projects evolve; mitigation: re-enrich on repeated read-miss.
- **Prompt-injection amplifier** (F1): without the author-tier defenses above, model-read hostile content could become durable, cross-session, injected knowledge. The tier system + injection filter + phase-2 human surface are the mitigations; until the human surface ships, `human`-tier content flows from human-authored files only.
- **Per-search LLM latency** on the primary path (L1 default): mitigated by cache + timeout fallback + `expand: false`; the p95 SLO gate verifies it; if the gate fails, the default must move toward enrichment-first or deterministic expansion (the blue team's stated flip condition).
- **Scale budgets**: maxQueryTrigrams/maxCandidates bound retrieval latency; index-size and list pagination bound storage/result growth — measured at the 500-1000 item corpus gate.
- Cursor "Memories" status is community-evidenced only; flagged above as such.

## References

- Benchmark synthesis and experiment: `research/memory-knowledge-seam/background/memory-seam-benchmark-synthesis.md` + `research/memory-knowledge-seam/experiments/memory-experiment/` (sibling workspace; reproducible via `node eval.mjs`, `node scale-eval.mjs`, `node variance.mjs`, `node build-human-set.mjs`, `node human-eval.mjs`; datasets: `distractors.json`, `human-queries.json`, `all-memories.json`).
- Generative Agents (recency × importance × relevance scoring), MemGPT/Letta (paging + sleep-time), LLMLingua (query-time compression), GraphRAG/HippoRAG (graph compaction), Anthropic context engineering ("context rot"), DeepSeek NSA (sparse attention).
- Reviews: independent architecture review (deepseek-v4-flash), red-team review (deepseek-v4-flash), a final adjudication (workflow-declared v4-pro; adjudicator's runtime persona reported v4-flash — see `research/memory-knowledge-seam/review/adjudication-v4pro.md`), and a red-blue adversarial round — red/blue on v4-flash (subagents) and red/blue on deepseek-v4-pro (direct API; see `research/memory-knowledge-seam/review/redteam-v4pro.md` and `research/memory-knowledge-seam/review/blueteam-v4pro.md`), plus the protocol adjudication rounds on deepseek-v4-pro — one verdict document per version in `research/memory-knowledge-seam/review/adjudications/` — all incorporated above.
