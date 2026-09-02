# dsh-knowledge-sqlite

[English](README.md) | [中文](README.zh.md)

Cross-session knowledge for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness): a `ctx.knowledge` service seam plus `knowledge_*` model tools, backed by SQLite FTS5 **trigram** retrieval (CJK substring search) with **L1 query expansion**.

Implements the [V1.11 knowledge seam proposal](https://github.com/NinjaSln-labs/dsh-plugins/blob/main/dsh-knowledge-sqlite/docs/DESIGN.md) (11-round reviewed design, community proposal — not an official DSH feature). Contract: `write/update/search/list/delete` + budget + events + error codes.

> MetaMath Harness local adaptation `0.1.6-metamath.1`: pinned to upstream commit `ac638c38`; durable writes, updates, and deletes are approval-gated; the production Profile hides the experimental `knowledge_probe` tool and disables query expansion to avoid implicit model calls. See [`UPSTREAM.md`](UPSTREAM.md) for provenance and the complete local delta.

```sh
dsh plugin add dsh-knowledge-sqlite
```

## Why trigram FTS5

DSH's current full-text search uses `unicode61`, which cannot match Chinese substrings. Measured on the project's evaluation suite (see [EXPERIMENTS](docs/EXPERIMENTS.md)):

| Retrieval stage | Hard rewritten queries (14, 512-item corpus) | Real human queries (17 targeted, 522-item corpus) |
|---|---|---|
| unicode61 (baseline, no CJK substring) | 0% | — |
| L0 pure lexical (trigram) | 7% | 65% |
| **L1 (default): + query expansion** | **21–64%** (prototype live: 43–64%) | **65%** (prototype live; reasoner variants measured 82%) |
| L2 (opt-in): + write-time enrichment | 50% | 88% (with n-enrichment) |

Acceptance gates (from V1.11): L1 recall@1 ≥ 30% on the hard set, ≥ 50% on the human set — both passed by the live prototype (kpro-2) and reproduced exactly by this bundle's SQLite layer (A 7% / C 21% / D 50% / human-A 65%, per-query rank identical).

## What it does

- **`knowledge_write`** — write a durable item; indexed immediately, zero LLM. `dedupeKey` upserts with stable id (`hash(workspace+scope+dedupeKey)`). **Ask-gated** (needs user approval; headless `approval=never` deployments auto-deny).
- **`knowledge_search`** — trigram OR + BM25, top-N; **L1 query expansion** by default (one small model call per query, cached per normalized query, `timeoutMs` fallback to lexical with `degraded: 'lexical'` metadata — never a tool error). `expand: false` or caller `variants` skips the call.
- **`knowledge_update`** — correction path; preserves id/provenance/stamps; `scope`/`dedupeKey` immutable after write.
- **`knowledge_list`** — auditability, cursor paging (newest first), `expired`/`deleted` flags.
- **`knowledge_delete`** — tombstone; expired items return `false`.
- **Events** — `knowledge/written` / `knowledge/updated` / `knowledge/deleted` with `{ id, scope, importance }`.
- **`knowledge_probe`** — evaluation-suite harness (stage-3 gates) that seeds the experiment corpus and reports arm recall + contract checks.

## Authorization & trust (V1.11)

- **Workspace isolation** — identity is the caller's canonical cwd (`session.header.cwd`); cross-workspace calls never see content.
- **Ask gating** — `knowledge_write`/`knowledge_update`/`knowledge_delete` go through the tools approval seam.
- **Global scope** — `allowedGlobalWriters` allowlist (agent/preset ids); headless denial is explicit `write-rejected`.
- **`authorTier`** — `human | explicit | derived | llm`, stamped by the tool layer (never caller input; spoofing → `write-rejected`). Hits carry `provenance: original | enriched` and `authorTier`.
- **Session scope** — scratch memory visible only to the owning session.

## Configuration

Plugin row config (all optional, defaults are the V1.11 proposal defaults):

```yaml
# cordis.patch.yml / profile row
- id: knowledge-sqlite
  name: 'dsh-knowledge-sqlite'
  config:
    gating: 'ask'                              # 'ask'：write/update/delete 经 approval 确认；'none'：跳过门控自动放行
    registerProbeTool: true                    # false：生产环境不注册 knowledge_probe
    databasePath: '/custom/data/knowledge.sqlite'   # 默认 $DSH_HOME/knowledge.sqlite（DSH_HOME 缺省 ~/.dsh）
    maxContentTokens: 2048
    queryExpansion:
      enabled: true
      model: ''                                # unset = session default model
      maxOutputTokens: 300
      timeoutMs: 3000   # 默认值（0.1.5 起）
      cache: true
    retrieval:
      topN: 20
      maxQueryTrigrams: 0                      # 0 = unlimited; cap 24 needs idf-priority truncation (see EXPERIMENTS)
      maxCandidates: 200
    authorization:
      allowedGlobalWriters: []                 # agent/preset ids allowed to write global scope
    corpusPath: 'research/memory-knowledge-seam/experiments/memory-experiment'   # probe corpus base (relative to workspace)
```

## Storage layout

- Single SQLite file (`items` + two FTS5 trigram tables: `items_fts_base` = content only, `items_fts_rich` = content + enrichment columns joined).
- Upsert uses `INSERT … ON CONFLICT DO UPDATE` (rowid stays stable so FTS links survive — `INSERT OR REPLACE` breaks them).
- Search filters `deleted`/TTL/workspace at query time; ranking is `bm25()`.
- `dedupeKey` uniqueness = `(workspace_id, scope, dedupe_key)` (non-partial unique index; SQLite NULLs don't conflict).

## Development

```sh
npm install
npm run build          # tsc（纯 TS，无需装饰器转换）
npm test               # vitest：38 项（store 19 + service 19）
node test-smoke.mjs    # SQLite 层冒烟：复现 A 7% / C 21% / D 50% / human-A 65% + 契约检查
```

测试覆盖（提案测试矩阵裁剪）：契约往返、dedupeKey 作用域 upsert（确定性 id）、打标伪造拒绝、
global allowlist、scope/dedupeKey 不可变、TTL（过滤/list 标记/过期 delete=false）、tombstone、
跨 workspace / session / global 隔离、missing-key、closed、maxContentTokens、分页、富化字段检索、
L1 扩展（mock llm：命中/缓存/超时降级/失败降级）、budget 截断、事件发射、ask 门控监听器、
probe 实验套件（A/C/D 确定性臂精确复现 + contract 全过）。

## Design & evidence

- [DESIGN](docs/DESIGN.md) — V1.11 proposal full text (community design, not official)
- [REVIEWS](docs/REVIEWS.md) — 11-round review chain summary (0C/0M/0m)
- [EXPERIMENTS](docs/EXPERIMENTS.md) — RESULTS-v3 + prototype verification (kpro-2, live L1, contract 11/11, ask-gate)
- Prototype workbench: `research/memory-knowledge-seam/experiments/prototype/` (SQLite blueprint, JS↔FTS5 calibration 0/72 mismatch, dynamic-plugin verification)
