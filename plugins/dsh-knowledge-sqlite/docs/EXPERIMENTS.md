# 实验与验证证据（EXPERIMENTS）

> dsh-knowledge-sqlite 的检索质量证据链：基准实验（RESULTS-v3）→ 动态原型验证 →
> 宿主 e2e（bundle 真实加载）。全部脚本与数据集可复现。

## 1. 基准实验（RESULTS-v3，2026-08-14）

语料：12 条真记忆（m1-m12，富化）+ 10 条提炼记忆（n1-n10）+ 500 条 DSH 仓库真实文档段落干扰项。

### 1.1 方差（门禁 1：≥10 次运行，LLM 难查询集 14 条 × 12 条语料）

| 臂 | recall@1 均值 | 范围 |
|---|---|---|
| C 查询扩展-only（L1） | **35.7%** | 29–43% |
| D 富化+扩展（L1+L2） | **63.6%** | 50–79% |

### 1.2 大语料（512 条：12 记忆 + 500 干扰项）

**LLM 难查询集（14 条）**：

| 臂 | recall@1 | recall@3 | MRR | precision@5 | NDCG@5 |
|---|---|---|---|---|---|
| A 纯词法 | 7% | 7% | 0.071 | 0.014 | 0.071 |
| B 写入富化 | 21% | 29% | 0.268 | 0.071 | 0.290 |
| C 查询扩展 | 21% | 29% | 0.264 | 0.071 | 0.287 |
| D 富化+扩展 | **50%** | **71%** | **0.607** | 0.143 | 0.635 |
| E PRF | 7% | **36%** | 0.202 | 0.071 | 0.242 |

**reasoner 交叉查询集（12 条）**：A 75% → D 100%。

### 1.3 人类查询集（20 条真实用户消息，17 条有目标，user-verified；522 条语料）

| 臂 | recall@1 | MRR |
|---|---|---|
| A 纯词法 | 65%（11/17） | 0.703 |
| C 查询扩展 | **82%**（14/17） | 0.853 |
| D 富化+扩展 | **88%**（15/17） | 0.882 |

none 查询（3 条）top1 全为空/干扰项——无误报。

### 1.4 修正后的召回全景

| 场景 | A 纯词法 | C 扩展 | D 富化+扩展 |
|---|---|---|---|
| LLM 难查询 × 12 条 | 7% | 36% | 64% |
| LLM 难查询 × 512 条 | 7% | 21% | 50% |
| reasoner × 512 条 | 75% | 92%* | 100% |
| 人类查询 × 522 条 | 65% | 82% | 88% |

（*reasoner × 12 条语料测得 92%）

## 2. 动态原型验证（kpro-2，2026-08-14）

沙箱内无法跑 node:sqlite → 三件套分层验证（详见 `research/memory-knowledge-seam/experiments/prototype/RESULTS-PROTOTYPE.md`）：

1. **SQLite 存储层**（`prototype/sqlite-trigram-verify.mjs`，真实 node:sqlite + FTS5 trigram）：
   精确复现 A 7% / C 21% / D 50% / human-A 65%（逐查询 rank 一致）
2. **JS BM25 校准**（`prototype/js-bm25-calibration.mjs`）：与 FTS5 bm25 **0/72 处 rank 不一致**
3. **动态插件链路**：write→trigram→search（L0 + L1-live 真实 llm.stream）；
   hard L1-live 43%/64%（≥30% 验收线）、human 65%（≥50%）、contract 11/11、ask 门控拒绝

关键发现（已并入 bundle 实现）：
- `maxQueryTrigrams` 顺序截断丢失长查询判别词（human A 65%→41%）→ 生产用 idf 优先截断或不限
- `llm.stream` 消息必须用 content blocks + source + id；finish reason 是对象
- workspace 身份优先调用方 cwd（`session.header.cwd`）
- 评估目标按 dedupeKey→id 映射解析（确定性 id 是 `k-<hash>` 前缀）

## 3. 宿主 e2e（bundle 真实加载，2026-08-14）

dsh-knowledge-sqlite 作为 profile bundle 挂载到 `dsh web`（`~/.dsh/profiles/web`）后的验证：

| 验证项 | 结果 |
|---|---|
| 工具注册 | knowledge_write/update/search/list/delete/probe ✓ |
| hard 确定性臂 | A 7% / C 21% / D 50%（真实 SQLite，逐查询 rank 一致）✓ |
| hard L1-live（实时扩展） | **64%**（9/14）✓（≥30% 验收线） |
| human A / L1-live | 65% / 65% ✓（≥50% 验收线） |
| contract | 12/12 ✓ |
| ask 门控 | knowledge_write 在 approval=never 下拒绝 ✓ |
| 扩展实测 | 31 次真实调用，26 成功（84%），5 超时降级（2.5s 超时），缓存生效 |

挂载排障记录（社区插件加载的坑：internal loader 依赖 + default export 必须是插件对象）：
`research/memory-knowledge-seam/experiments/prototype/MOUNTING-NOTES.md`。

## 4. 复现

```sh
# 基准实验（memory-experiment 目录）
node eval.mjs            # 五臂 × 12 条（LLM 难查询）
node scale-eval.mjs      # 四臂 × 512 条 + PRF
node variance.mjs        # 10 次方差（需要 API key）
node human-eval.mjs      # 人类查询评估（22 记忆 + 500 干扰项）

# 原型验证（research/memory-knowledge-seam/experiments/prototype 目录）
node sqlite-trigram-verify.mjs   # SQLite 层基线（无 API 依赖）
node js-bm25-calibration.mjs     # JS↔FTS5 校准（无 API 依赖）

# bundle（dsh-plugins/dsh-knowledge-sqlite）
npm test                 # vitest 38 项（store 19 + service 19）
node test-smoke.mjs      # SQLite 冒烟（7/21/50/65 + 契约）
# 宿主：knowledge_probe { suite: 'variance' | 'latency' | 'all' }
```

## 5. 验收门禁对照（阶段 3 状态，2026-08-14 宿主实测）

| 门禁（V1.11） | 目标 | 状态 |
|---|---|---|
| L1 recall@1（hard） | ≥30% 均值，无单次 <20% | **PASS**：10 轮方差均值 **56%**，范围 43–71%（deepseek-v4-flash 实时扩展；基准 C 臂 35.7%±[29-43] 为 reasoner 模型） |
| human 集 L1 | ≥50% | 宿主 65% ✓ |
| 人类集 precision@1 | ≥80%（信息性） | 待 promotion 补测（0.1.3 已补测，见 §6） |
| p95 L1 延迟 | ≤2.0s（4 路并发，人类查询集） | **FAIL**：真实扩展测量 2171ms / 2293ms（fresh 清缓存两次），超目标 ~10-15%；缓存命中后扩展延迟≈0（生产同查询复用缓存显著降低） |
| 写入即检索（零 LLM） | AC | ✓ |
| 授权/打标/错误码/事件 | AC | contract 12/12 ✓ |
| 实验套件入库 | AC | ✓ |

### p95 延迟门禁分析（未过，如实记录）

- 测量口径：人类查询集 17 条，4 路并发，`expand: true`，非降级查询的扩展延迟（V1.11：degraded 查询排除在 p95 外）。
- 数据：两次 fresh 测量 p95 = 2171ms / 2293ms；非降级查询均值 ~1.7-1.8s；超时率 ~12%（2.5s timeoutMs）。
- **根因是外部 LLM API 首包延迟**（deepseek 流式 TTFT 918-2293ms），非实现缺陷。V1.11 设计假设"p95 2.0s < timeoutMs 2.5s"在当前环境的头部关系已破坏（实测 p95 2.3s）。
- 缓解选项（部署时配置）：① `queryExpansion.timeoutMs` 提至 3000 恢复头部余量、降低降级率；② `queryExpansion.model` 换更快路由；③ 生产同查询缓存命中后扩展延迟≈0（真实使用中 p95 接近词法检索）。promotion 重测建议：网络环境稳定后 fresh 重跑，或按真实使用（缓存）口径评估。

## 6. 0.1.3 发布后重测（2026-08-16，宿主实测，bundle 0.1.3）

发布 0.1.3（probe 语料路径修复 + human 套件 precision@1/none 上报）后的门禁重测，
全部经 `knowledge_probe`（真实 SQLite + deepseek-v4-flash 实时扩展）：

| 套件 | 结果 |
|---|---|
| hard 确定性臂 | A 7% / C 21% / D 50% ✓ 精确复现（逐查询 rank 一致） |
| hard L1-live | **50%**（7/14，3 条降级）≥30% PASS |
| human A | 65%（11/17）✓ 复现 |
| human L1-live | **59%**（10/17，9 条降级）≥50% PASS |
| 人类集 precision@1（信息性） | A 65% / L1-live 59%（单目标套件口径 ≡ recall@1，如实并列；<80% 未过，记录为 promotion 观察项） |
| none 无误报 | h1/h4/h5 top1 全空，**无误报 PASS**（新增检查） |
| p95 L1 延迟（fresh，4 路并发） | **2380ms**（非降级 8 条均值 2071ms，9/17 超时降级）> 2000ms **FAIL**——与 0.1.2 时代测量一致，根因不变 |
| contract | 12/12 ✓ |

观察：
- 确定性臂跨版本精确复现，SQL 层检索无回归。
- 降级率随网络抖动波动大：hard 21%（3/14）、human 53%（9/17）——0.1.2 时代实测为 16%（5/31）；
  降级查询走词法回退，命中仍可用（human 59% 中降级查询的命中部分来自 trigram 词法本身）。
- precision@1 信息性门禁（≥80%）首次宿主实测：A 65% / L1-live 59%，未达 80% 线
  （基准 88% 为离线 reasoner 富化+扩展 D 臂）；如实记录，待 promotion 用更强扩展模型或 L2 富化复核。
- p95 延迟门禁仍 FAIL：根因（外部 LLM TTFT 超 2.5s timeoutMs）与缓解选项见 §5 分析，未变。

## 7. 0.1.4 诊断迭代（2026-08-16，宿主实测，bundle 0.1.4）

目标：分离"扩展模型能力"与"实时降级"两个变量——human 套件新增 C 臂
（离线 reasoner variants，`human-expanded.json`，deepseek-chat 生成、与基准同口径）。

### 7.1 human 套件三臂（fresh）

| 臂 | recall@1 | 说明 |
|---|---|---|
| A 纯词法 | **65%**（11/17）| 确定性，跨版本复现 |
| C 离线 reasoner variants | **71%**（12/17）| 确定性；宿主与本地 SQLite 评估逐 rank 一致 ✓ |
| L1-live flash 实时 | **65%**（11/17）| 5/17 降级（h2,h6,h8,h10,h17） |

诊断结论：
- **模型能力差距成立**：C − A = +6 点（reasoner variants 把 h18 从 rank5 拉到 rank1、h9 从 miss 拉到 rank2）；
- **降级拖累明显**：本轮 L1-live 5/17 降级 → 恰好跌回 A 臂水平（65%），扩展增益被完全抵消；
- precision@1（信息性）：A 65% / C 71% / L1-live 65%；none 无误报 PASS（3/3 top1 空）。
- C 臂批次方差：基准历史抽样 82%（14/17），本批次 71%（12/17）——LLM 生成物抽样波动，
  V1.11 人类集 C/D 臂方差条款适用；更换 variants 需记录批次（fixture README 已注明）。

### 7.2 variance 复跑（10 轮 × 14 条 hard，每轮清缓存）

- 均值 **49%**（范围 36-71%），门禁双 PASS（≥30% 均值、无单次 <20%）。
- 与 0.1.2 时代 56%（43-71%）对比：均值下降由**降级污染**驱动——本轮每轮 1-9 条查询
  扩展超时降级（中位 5/14），run 级 recall 与降级数强相关；
- 关键观察：**run 1 仅 1/14 降级时达到 71%**（10/14）——扩展正常时 flash+富化在 hard 集
  达到/超过离线 D 臂（50%）水平，说明实时扩展本身的边际质量不输离线 reasoner 批次，
  当前瓶颈在"能不能在 2.5s 内拿到扩展结果"，而非扩展模型能力。
- 后续优化优先级由此数据进一步明确：**先解决降级/延迟（缓存持久化 + timeoutMs），
  再谈更强扩展模型**（换模型只影响未降级查询的边际收益，且可能加剧 TTFT）。

## 8. 0.1.5 可用性迭代（2026-08-16，宿主实测，bundle 0.1.5）

实现：L1 扩展缓存持久化（SQLite `expansion_cache` 表，workspace 隔离；内存+持久两级，
`fresh`/variance 清两级）+ `queryExpansion.timeoutMs` 默认 2500 → 3000。

### 8.1 缓存路径验证（核心收益）

| 验证 | 结果 |
|---|---|
| human fresh（timeout 3000） | 12/17 降级，L1-live 59%（A 65% / C 71%） |
| human 非 fresh | 缓存查询结果与首次逐 rank 一致（复用确定性）；降级 11/17（h15 实时恢复） |
| latency 非 fresh（生产口径） | **缓存 6 条全部 0ms**（h7/h9/h11/h13/h15/h18）；非降级 p95 2517ms（h19 实时） |
| `expansion_cache` 表 | 7 行落库 ✓（6 条 human + h19），workspace 隔离键正确 |
| 跨进程复用 | 单元测试覆盖（新服务实例同 DB 命中持久缓存）；表数据跨重启存在 |

**缓存收益成立**：同查询第二次起 0 延迟、零降级、结果稳定——真实使用中命中查询
p95 ≈ 0；未命中查询仍是实时扩展的原始成本。

### 8.2 timeoutMs 3000 的诚实结论（未达预期）

- latency fresh：**13/17 降级（76%）**，非降级 4 条全部 2.78-2.95s，p95 **2946ms**——
  比 2500ms 时代（9/17 降级、p95 2380ms）更差；
- 根因：当前网络窗口外部 LLM **TTFT 恶化至 2.8-3.0s+**（本会话内从 918-2565ms 退化），
  timeout 3000 仍不够；"调参不能对抗网络退化"——timeout 再上调只会把 p95 推得更高。
- 门禁影响：fresh 口径 p95 依旧 FAIL（非实现缺陷，环境变量）；生产口径（缓存命中）≈0。
- **路线修正**：timeout 调整到此为止（边际无效）；第 4 步"扩展模型路由实测"优先级提升——
  目标从"更强"改为"**更快**"（第三方路由 TTFT 实测），从根上解决降级。
- 回顾：p95/降级门禁连续 3 次记录 FAIL——流程层面建议把门禁口径修订（生产缓存口径）
  或网络条件声明为环境变量，列入后续决策项（第 5 步）。

## 9. 扩展延迟根因链与 0.1.6 修复（2026-08-16）

### 9.1 根因（问题深挖实测闭环，修正此前归因）

扩展请求的 provider/model **跟随会话默认模型**（expand.ts：`provider = 会话默认 provider`，
`model = config.model ?? 会话默认 model`）。此前各版"外部 LLM TTFT"归因是**误读**——
latencyMs 是完整调用时长而非首包；且未核对实际路由。curl 同时刻对照：

| 路由 | TTFT | 总耗时 | 说明 |
|---|---|---|---|
| api.deepseek.com 官方直连（v4-flash） | **~107ms** | 1.0-1.5s | 直连/代理均快；无 thinking |
| commandcode 网关 gpt-5.6-sol（旧默认） | 2.4-3.1s | 3.2-3.9s | timeout3000 下 76% 降级 |
| opencode-go v4-flash thinking 全开 | 3.4s | 11.3s | `reasoning:true` catalog，timeout3000 下 100% 降级 |
| opencode-go v4-flash thinking disabled | ~2.0s | ~3.4s | 网关自身 TTFT ~2s 为物理属性 |

结论链：主模型切到 reasoning/中转路由 → 扩展隐性跟随 → TTFT 超 timeout → 大规模降级。
网络/代理/官方 API 均无辜（官方直连 TTFT 107ms 反例证伪）。

### 9.2 修复（0.1.6）与验证

- `reasoningEffort: 'off'` → llm-pi-ai 将 'off' 翻译为省略 reasoning → pi-ai deepseek 分支
  `thinking: { type: 'disabled' }`——opencode-go v4-flash 总耗时 11.3s → 3.4s ✓
- 部署配置固定 `queryExpansion.model: 'deepseek-v4-flash'`（不配 provider，跟随会话默认，
  用户决策保留 opencode-go 默认）
- 宿主 latency fresh（off 后）：降级 9/17（53%），非降级 2.0-3.0s，p95 3001ms——
  **网关物理 TTFT ~2s 未解**；human fresh L1-live 59% 无退化
- 缓存兜底不变：命中查询 0 延迟零降级（§8）

### 9.3 悬而未决（交接 HANDOFF.md §3 决策项，本地私有，未追踪）

- 决策 A/B：接受网关 TTFT ~2s vs 0.1.7 加 `queryExpansion.provider` 走官方直连（107ms）；
  用户此前倾向不直连官方（「官方也可能思维链全开」）——已被本节 curl 实测排除，待用户拍板
- p95 ≤2.0s 门禁口径修订（fresh vs 生产缓存口径）：连续 FAIL 均为网关环境变量，建议修订口径
