# CHANGELOG — dsh-knowledge-sqlite

## 0.1.6 (2026-08-16)

- **fix**: 扩展请求显式关闭思维链（`reasoningEffort: 'off'` → pi-ai `thinking: {type:'disabled'}`）。
  根因：扩展 provider/model 跟随会话默认，若默认路由是 reasoning 模型（如 opencode-go 的
  deepseek-v4-flash，`reasoning: true`），thinking 预热使 TTFT 高达 3.4s / 总耗时 11.3s，
  timeout 3000 下 100% 降级（详见 EXPERIMENTS §9 根因分析）；关闭后退化为普通生成。
- 部署配套：profile patch 配置 `queryExpansion.model: 'deepseek-v4-flash'`（默认 provider
  内优先 v4-flash，不配 provider——跟随会话默认路由）。
- **test**: +2（扩展请求携带 reasoningEffort=off；model 显式配置生效、provider 跟随默认；
  mock llm 记录路由参数）。
- 回顾：本次根因是"配置跟随主模型"这一数据流决策，主模型换推理模型后扩展隐性退化——
  新增速查表行（见仓库根 DEVELOPMENT.md）。

## 0.1.5 (2026-08-16)

- **feat**: L1 扩展缓存持久化——SQLite `expansion_cache` 表（按 workspace 隔离，
  跨进程/重启复用）：同查询第二次起 **0 延迟、零降级**（内存 + 持久两级；
  `fresh`/variance 语义同时清两级，保证评估独立性）。
- **change**: `queryExpansion.timeoutMs` 默认 2500 → 3000（降低超时降级率；
  fresh 口径 p95 右移、生产口径（缓存命中）≈0——权衡分析见 EXPERIMENTS §8）。
- **test**: store 3 项（roundtrip/跨 ws 隔离/upsert 覆盖、clear、坏数据）+
  service 1 项（新服务实例同 DB 命中持久缓存、fresh 后重建）。
- 回顾：缓存层从"进程内存"到"持久化"是数据流决策，隔离键（workspace）与内容层一致，
  无新坑入表。

## 0.1.4 (2026-08-16)

- **feat**: human 套件新增 C 臂诊断——离线 reasoner variants（`human-expanded.json`
  落盘入库，deepseek-chat 生成口径与基准一致），分离"扩展模型能力"与"实时降级"两个变量；
  precision@1 与 none 无误报检查同步覆盖 C 臂。
- 实测：本批次 C 臂 12/17 (71%)（基准历史抽样 82%——C/D 臂有 LLM 抽样方差，V1.11 条款；
  详见 EXPERIMENTS §7）。
- 回顾：见仓库根 DEVELOPMENT.md 速查表"语料迁移后路径未同步"行（fixture 同步流程已固化）。

## 0.1.3 (2026-08-16)

- **fix**: probe 语料默认路径与工作区布局一致 —— 语料迁移后 bundle 默认 `corpusPath`、
  测试 `CORPUS`、`test-smoke.mjs` 三处仍指向不存在的 `research/memory-experiment`，
  导致宿主 `knowledge_probe` 套件 ENOENT、`npm test` probe 用例失败。全部改指
  `research/memory-knowledge-seam/experiments/memory-experiment`。
- **test**: 实验语料以 fixture 形式入库（`tests/fixtures/corpus/`，逐字拷贝 + 同步说明），
  单测与冒烟脱离仓库外 `research/` 目录、CI 可跑。
- **feat**: human 套件上报 precision@1（V1.11 信息性门禁 ≥80%，单目标套件口径 ≡ recall@1，
  两臂并列如实报告）与 none 查询无误报检查（top1 必须为空或非记忆条目）。
- 回顾：发版物与工作区布局脱节是"仓库路径已修、测试/发布物未同步"的同类坑
  （详见仓库根 DEVELOPMENT.md 速查表新行）。

## 0.1.2 (2026-08-14)

- **fix**: 工具层 strict JSON —— `-0`/NaN bm25 分数归一化、`undefined` 字段省略
  （search/list 直接工具调用），测试对照 `snapshotJsonValue`。

## 0.1.1 (2026-08-14)

- **feat**: `gating` 配置（默认 `ask` 符合 V1.11；`none` 供受信部署自动放行）。

## 0.1.0 (2026-08-14)

- **feat**: 跨会话知识插件（V1.11 契约）—— `ctx.knowledge` 服务 + `knowledge_*` 工具，
  SQLite FTS5 trigram + L1 查询扩展。
- **feat**: `knowledge_probe` 实验套件（seed/hard/human/contract），后补 variance（10 轮 L1
  门禁）与 latency（4 路并发 p95）套件。
- 阶段 3 门禁：L1 hard 均值 56% PASS、human 65% PASS、p95 延迟 FAIL（如实记录，外部 LLM TTFT）。
