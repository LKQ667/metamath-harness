---
name: grill-ai-review
description: Self-interrogate and improve AI-written code after implementation to catch missed requirements, unreviewed files, hidden regressions, needless abstractions, duplicated logic, weak tests, and codebase-damaging complexity. Use when the user asks Codex to grill, self-review, stress-test, harden, or optimize its own code changes.
user-invocable: true
disable-model-invocation: true
---

Run a self-contained `/grilling` pass on your own code changes.

Ask and answer the hard questions yourself. Inspect the repository for answers instead of asking the user.

For each risk, name the concrete file, diff, behavior, or test involved. Fix real issues you find, keep diffs minimal, and avoid speculative rewrites.

Focus on missed scope, untouched call sites, broken contracts, duplicated logic, needless abstractions, hidden state, config/build/migration impact, weak tests, and rollback risk.

Stop only after verification and a concise report of questions asked, answers found, fixes made, and remaining risk.

## 数学建模比赛评委分支

当用户手动调用本 Skill，且请求包含 `dsh.mathmodel.request/v1` 或数学建模比赛评审意图时，使用本分支；其余请求保持上面的代码自审流程。结构化请求的 `skill` 必须为 `grill-ai-review`，直接消费 `competition`、`official_rules_path`、`submission_path`、`review_depth`、`include_score`、`reference_excellent_papers`、`focus` 和 `userNotes`，不得重复询问。

先读取提交材料、赛题和可获得的官方赛事规则。评分依据优先级固定为：当届官方规则与赛题要求 > 用户明确约束 > 通用数学建模评审量表。缺少官方规则时必须醒目标注“未提供官方评分标准，本次采用通用量表”，不得伪装成官方评分。

必须启动三个相互独立的专项子评委并行审查，再由主审汇总；不得让主审先给结论影响专项评委，也不得用一个角色模拟三份结果：

1. 规则与完整性评委：核对题目逐问响应、官方格式、数据和引用来源、必需声明、交付完整性及硬性违规。
2. 模型与计算评委：核对假设、变量、公式、约束、算法、代码/结果一致性、敏感性与鲁棒性；未实际运行的内容必须标为“未复现”，不得伪造复现成功。
3. 论文表达与图表评委：核对摘要、逻辑链、结果解释、图表选择与可读性、公式符号、引用对应和评委阅读成本。

每名专项评委必须独立输出：适用评分依据、分项分数及权重（`include_score=false` 时改为等级）、至少三条带页码/章节/文件定位的证据、硬伤、主要优点、置信度和按影响排序的整改建议。无法观察的维度标记“证据不足”，不得按想象补分。

主审只在三份专项意见完成后工作，负责统一官方权重、列出分歧及裁决依据、汇总总分/等级、给出一票否决项、前五项整改优先级和复核清单。主审必须追问自己的结论：是否遗漏赛题小问、是否把写作问题误判为模型问题、是否把未复现当成错误、是否有分数与证据不匹配；发现问题时回查材料后修正。

若 `reference_excellent_papers=true`，先从赛题或提交材料识别题号，再调用 `../_shared/scripts/discover_excellent_papers.py --competition <competition> --problem <识别到的题号> --limit 2`；无法可靠识别题号时省略 `--problem` 并把 `problem_match=false` 明确列为不确定性。只读取 `<DSH_HOME>/往年优秀论文/<赛事>/` 中发现脚本返回的样本，并执行 `../_shared/references/excellent-paper-policy.md`。报告必须列出返回状态、实际样本相对路径、赛事、题号、年份和是否精确匹配；返回 `catalog_missing`、`catalog_invalid`、`no_matching_sample`、`file_missing` 或 `hash_mismatch` 时写明“暂无样本”及原因，继续使用规则量表，不得阻断评审。开关关闭时不得扫描或读取论文库。

评审默认只读，不直接改写提交材料。最终报告必须包含三份专项评审、主审汇总、证据定位、整改顺序与剩余不确定性；若用户随后明确要求修复，再按主审优先级实施并重新评分。
