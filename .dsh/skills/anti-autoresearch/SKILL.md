---
name: anti-autoresearch
description: 仅手动触发的论文科研诚信取证审计 Skill。只有当用户明确输入 `$anti-autoresearch` 或明确点名“使用 anti-autoresearch Skill”时才使用；即使用户提出论文造假嫌疑、科研诚信、数值核验、引用核验、实验复现或证明审查等请求，也禁止自动触发。触发后可检查数值与统计自洽、正文和表格矛盾、方法范围漂移、基线公平性、实验结果与代码不一致、虚构或错引文献、证明推导漏洞、数据泄漏、选择性报告、重复发表线索及可疑 AI 写作痕迹；只输出待人工复核的证据与风险，不认定作者造假。
user-invocable: true
disable-model-invocation: true
---

# Anti-Autoresearch：论文诚信审计

把原仓库的11个审计 Skill 和总控流程作为一个 DeepSeek Harness Skill 执行。保持只读审计，不修改被审论文，不把异常直接表述为“造假”。

## DeepSeek Harness mathmodel 入口契约

若手动调用文本包含 `dsh.mathmodel.request/v1`，其 `skill` 必须为 `anti-autoresearch`，直接消费 `material_path`、`evidence_level`、`audit_scope`、`report_depth`、`include_recheck_plan` 和 `userNotes`，不得重复询问。卡片的 `evidence_level` 是用户预计提供的材料范围，不是结论权限；必须由 `artifact_manifest.json` 按实际可见材料确定 L0/L1/L2，实际等级较低时自动收紧结论并明确缺失材料，禁止按卡片标签抬高等级。

`report_depth=代码结果级审计`（兼容旧草稿值“复现级审计”）只表示在 L2 检查论文、代码、日志和已有结果文件的一致性，不代表 L3 完整复现，也不得承诺复现实验。`audit_scope` 只决定加载哪些维度；未运行的维度必须进入局限说明。`include_recheck_plan=false` 时仍保留每条 finding 必需的 `recommended_human_check`，只省略额外汇总计划，因为该字段属于证据契约而非可选装饰。

卡片标题中的“风险审查”和用户口语中的“造假嫌疑”均只表示筛查意图。报告只能写带 claim/span 的异常、不一致、证据不足或需要核查，并给出可能的无辜解释；不得输出作者身份概率、AI 生成率或“造假/欺诈已证实”等裁决。

## 基本原则

1. 先建立统一证据账本，再进行任何判断。
2. 每条高于 `info` 的发现必须引用 `claims.json` 中真实存在的 `claim_id` 和原文片段。
3. 区分可观测等级：L0 仅 PDF/文本，L1 有 LaTeX，L2 同时有代码和结果；不得在低等级声称已验证代码级问题。
4. 语言模型只提出发现；最终等级只由 `scripts/adjudicate_findings.py` 计算。
5. AI 文风、版面和新颖性线索不作为学术不端结论。
6. 报告使用“异常”“不一致”“需要核查”，不得使用“作者造假”“欺诈已证实”等定罪措辞。

开始前读取：

- `references/integrity-forensics-contract.md`：证据和输出契约。
- `references/observability-levels.md`：L0/L1/L2 的结论边界。
- `references/hack-pattern-taxonomy.md`：允许使用的风险模式编号。
- `references/reviewer-independence.md`：审计者与裁决器分工。

## 输入处理

接受论文目录、`.pdf`、`.tex` 或纯文本。PDF 若尚无文本层，优先用 `pdftotext -layout` 提取为同目录 `paper.txt`；无法提取时说明依赖缺失，不得假装读取成功。目录中存在源文件、代码、配置、日志和结果时一并纳入，但保持只读。

## 执行流程

### 1. 运行确定性骨架

运行：

```powershell
python scripts/run_deterministic_audit.py "<论文文件或目录>"
```

该脚本生成：

- `artifact_manifest.json`
- `claims.json`
- `consistency-audit.deterministic.findings.json`
- `presentation-signals.deterministic.findings.json`
- `stat-consistency.deterministic.findings.json`
- `ai-style-impressions.deterministic.findings.json`
- `report.json`
- `REPORT.md`

脚本失败时停止并报告真实错误，不手工伪造缺失产物。

### 2. 按需做语义审计

根据用户目标和材料读取对应参考文件，不要一次加载全部：

| 审计目标 | 读取文件 |
|---|---|
| 证据账本与声明抽取 | `references/audit-evidence-ledger.md` |
| 数字、表格、摘要与正文矛盾 | `references/audit-consistency-audit.md` |
| 引用虚构、错引、撤稿引用 | `references/audit-citation-forensics.md` |
| 缺失、过弱或不公平基线 | `references/audit-baseline-comparison-audit.md` |
| 代码、结果、占位数据、幽灵实验 | `references/audit-experiment-forensics.md` |
| 证明、推导、符号和隐含假设 | `references/audit-proof-derivation-forensics.md` |
| 数据泄漏、裁判模型、选择性报告 | `references/audit-eval-design-forensics.md` |
| 重复表格、模板残留、版面信号 | `references/audit-presentation-signals.md` |
| AI 写作风格印象，零裁决权重 | `references/audit-ai-style-impressions.md` |
| 最强反方审稿意见 | `references/audit-adversarial-case-builder.md` |
| 既有工作重叠、重复发表线索 | `references/audit-novelty-duplication-advisory.md` |

DSH 没有上游文档所写的 Claude `/skill` 或 `mcp__codex__codex` 时，直接由当前模型按相同检查表完成该维度，并明确记录“未进行跨模型独立复核”。不得声称使用了不存在的工具。

### 3. 写入语义发现

每个维度写成独立 JSON 数组，元素遵循 `schemas/finding.schema.json`。至少包含：

- `finding_id`
- `skill`
- `pattern_id`
- `severity_proposed`
- `dimension`
- `title`
- `description`
- `evidence`，其中包含真实 `claim_id` 与原文 `span`
- `observability_level_required`
- `false_positive_risk`
- `recommended_human_check`

无法验证时降为 `info` 或写入局限，不得用推测补齐证据。

### 4. 重新裁决

将确定性和语义 `*.findings.json` 一起传给：

```powershell
python scripts/adjudicate_findings.py --findings <发现文件...> --ledger <claims.json> --paper-id <论文标识> --observability-level <0|1|2> --out <report.json> --md <REPORT.md>
```

只把该脚本生成的结果称为总体裁决。若关键维度未运行，在报告局限中逐项说明。

## 交付要求

先给出观测等级和材料范围，再列出发现。每条发现必须包含位置、原文证据、计算或核验过程、可能的无辜解释、建议人工索取的材料。结尾明确说明：报告是风险筛查和同行评审辅助，不构成对学术不端的认定。

## 更新来源

本 Skill 合并自 `wanshuiyin/Anti-Autoresearch`，保留 MIT 许可证。更新时比较上游 `skills/`、`tools/`、`references/` 和 `schemas/`；继续保持单一顶层 `SKILL.md`，不要把上游多个 Skill 目录直接嵌套到 DSH Skills 根目录。
