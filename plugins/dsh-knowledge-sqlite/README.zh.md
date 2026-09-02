# dsh-knowledge-sqlite

[English](README.md) | [中文](README.zh.md)

[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 的跨会话知识插件：`ctx.knowledge` 服务接缝 + `knowledge_*` 模型工具，基于 SQLite FTS5 **trigram** 检索（中文子串匹配）+ **L1 查询扩展**。

实现了 [V1.11 知识接缝提案](https://github.com/NinjaSln-labs/dsh-plugins/blob/main/dsh-knowledge-sqlite/docs/DESIGN.md)（11 轮评审的设计，社区提案——非 DSH 官方功能）。契约：`write/update/search/list/delete` + budget + 事件 + 错误码。

> MetaMath Harness 本地适配版 `0.1.6-metamath.1`：固定上游提交 `ac638c38`，持久写入、更新、删除均需确认；生产 Profile 隐藏实验工具 `knowledge_probe`，并关闭查询扩展，避免检索时隐式调用模型。完整来源与差异见 [`UPSTREAM.md`](UPSTREAM.md)。

```sh
dsh plugin add dsh-knowledge-sqlite
```

## 为什么用 trigram FTS5

DSH 现有的全文检索使用 `unicode61`，无法匹配中文子串。在项目评测套件上的实测（见 [EXPERIMENTS](docs/EXPERIMENTS.md)）：

| 检索阶段 | 改写难题集（14 题，512 条语料） | 真实人工查询（17 条定向，522 条语料） |
|---|---|---|
| unicode61（基线，无 CJK 子串） | 0% | — |
| L0 纯词法（trigram） | 7% | 65% |
| **L1（默认）：+ 查询扩展** | **21–64%**（原型在线：43–64%） | **65%**（原型在线；reasoner 变体实测 82%） |
| L2（可选）：+ 写入时富化 | 50% | 88%（带 n-富化） |

验收门槛（来自 V1.11）：难题集 L1 recall@1 ≥ 30%、人工集 ≥ 50%——在线原型（kpro-2）与本插件的 SQLite 层均精确复现并通过（A 7% / C 21% / D 50% / human-A 65%，逐查询排名一致）。

## 功能

- **`knowledge_write`** — 写入持久条目；立即入索引，零 LLM。`dedupeKey` 以稳定 id upsert（`hash(workspace+scope+dedupeKey)`）。**Ask 门控**（需用户批准；headless `approval=never` 部署自动拒绝）。
- **`knowledge_search`** — trigram OR + BM25 取 Top-N；默认 **L1 查询扩展**（每次查询一次小模型调用，按归一化查询缓存，`timeoutMs` 超时降级为词法检索并带 `degraded: 'lexical'` 元数据——绝不会变成工具报错）。`expand: false` 或调用方提供 `variants` 可跳过该调用。
- **`knowledge_update`** — 修正路径；保留 id/溯源/打标；`scope`/`dedupeKey` 写后不可变。
- **`knowledge_list`** — 可审计性，游标分页（新条目在前），`expired`/`deleted` 标记。
- **`knowledge_delete`** — tombstone；过期条目返回 `false`。
- **事件** — `knowledge/written` / `knowledge/updated` / `knowledge/deleted`，带 `{ id, scope, importance }`。
- **`knowledge_probe`** — 评测套件工具（阶段 3 门禁）：装载实验语料，报告各臂 recall + 契约检查。

## 授权与信任（V1.11）

- **工作区隔离** — 身份是调用者的规范化 cwd（`session.header.cwd`）；跨工作区调用永远看不到内容。
- **Ask 门控** — `knowledge_write`/`knowledge_update`/`knowledge_delete` 走工具批准接缝。
- **全局范围** — `allowedGlobalWriters` 白名单（agent/preset id）；headless 拒绝为显式 `write-rejected`。
- **`authorTier`** — `human | explicit | derived | llm`，由工具层打标（绝不来自调用方输入；伪造 → `write-rejected`）。命中带 `provenance: original | enriched` 与 `authorTier`。
- **会话范围** — 仅所属会话可见的草稿记忆。

## 配置

插件行配置（全部可选，默认值为 V1.11 提案默认值）：

```yaml
# cordis.patch.yml / profile row
- id: knowledge-sqlite
  name: 'dsh-knowledge-sqlite'
  config:
    gating: 'ask'                              # 'ask'（默认）：write/update/delete 经 approval 确认；'none'：跳过门控自动放行
    registerProbeTool: true                    # false：不向生产 Agent 暴露实验工具 knowledge_probe
    databasePath: '/custom/data/knowledge.sqlite'   # 默认 $DSH_HOME/knowledge.sqlite（DSH_HOME 缺省 ~/.dsh）
    maxContentTokens: 2048
    queryExpansion:
      enabled: true
      model: ''                                # 未设置 = 会话默认模型
      maxOutputTokens: 300
      timeoutMs: 3000   # 默认值（0.1.5 起）
      cache: true
    retrieval:
      topN: 20
      maxQueryTrigrams: 0                      # 0 = 不限；上限 24 需 idf 优先截断（见 EXPERIMENTS）
      maxCandidates: 200
    authorization:
      allowedGlobalWriters: []                 # 允许写入 global 范围的 agent/preset id
    corpusPath: 'research/memory-knowledge-seam/experiments/memory-experiment'   # probe 语料根（相对工作区）
```

## 存储布局

- 单个 SQLite 文件（`items` + 两张 FTS5 trigram 表：`items_fts_base` = 仅正文，`items_fts_rich` = 正文 + 富化列联合）。
- Upsert 用 `INSERT … ON CONFLICT DO UPDATE`（rowid 保持稳定，FTS 链接得以存活——`INSERT OR REPLACE` 会破坏它们）。
- 查询时过滤 `deleted`/TTL/workspace；排序用 `bm25()`。
- `dedupeKey` 唯一性 = `(workspace_id, scope, dedupe_key)`（非部分唯一索引；SQLite 的 NULL 不冲突）。

## 开发

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

## 设计与证据

- [DESIGN](docs/DESIGN.md) — V1.11 提案全文（社区设计，非官方）
- [REVIEWS](docs/REVIEWS.md) — 11 轮评审链摘要（0C/0M/0m）
- [EXPERIMENTS](docs/EXPERIMENTS.md) — RESULTS-v3 + 原型验证（kpro-2、在线 L1、契约 11/11、ask 门控）
- 原型工作台：`research/memory-knowledge-seam/experiments/prototype/`（SQLite 蓝图、JS↔FTS5 校准 0/72 无偏差、动态插件验证）
