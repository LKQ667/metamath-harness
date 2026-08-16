---
name: grill-with-docs
description: Run /grilling in /plan with tool/requestUserInput and isOther, use analysis-only $domain-modeling, and produce a decision-complete Markdown plan. Use when a plan must be fully clarified without modifying project files.
user-invocable: true
disable-model-invocation: true
---

# Grill with Docs

Run `/grilling` in `/plan`. Do not modify files, configuration, or repository state, and do not implement the plan.

For each question, use Codex's `tool/requestUserInput` with one clear question and 3 meaningful options, including `isOther`. Briefly answer custom responses, then continue; never treat them as permission to exit before all planned questions are resolved.

During grilling, invoke `$domain-modeling` in analysis-only mode. Fold its findings into the plan and turn unresolved domain decisions into subsequent questions.

Once the goal, scope, design, interfaces, failure handling, compatibility, tests, and acceptance criteria are decision-complete, output one self-contained Markdown plan. State unresolved assumptions explicitly.

Make the final plan execution-ready for an AI with no prior context: ground it in repository evidence, preserve all decided requirements and rationale, order implementation work by dependency, and give each task enough context, affected locations, constraints, and verification criteria to execute without guessing. Adapt the structure and detail to the task; do not prescribe implementation choices that remain context-dependent.

## 数学建模新手分支（赛题思路启发）

当用户手动调用本 Skill，且请求包含 `dsh.mathmodel.request/v1`、数学建模赛题或“赛题思路启发”意图时，使用本分支；其余请求保持上面的通用规划流程。结构化请求的 `skill` 必须为 `grill-with-docs`，卡片已锁定的 `material_path`、`objective`、`beginner_level`、`question_budget`、`output_depth`、`existing_idea` 和 `userNotes` 不得重复询问。

先读取当前工作区内的赛题材料和用户已有想法。把用户当作完全小白，用通俗中文解释术语，但不降低事实、假设和证据标准；能从材料、目录、数据字典或官方规则查到的信息必须自行查明，禁止把检索工作反问给用户。

三种方法按阶段组合使用，不作为互斥模式：

1. 笛卡尔式清零：从原文提取已知事实、交付目标、未知量、可控量、约束、数据来源和评价指标，区分原文事实与暂定假设。此阶段以阅读和整理为主，不把每个未知量都变成问题。
2. 苏格拉底式拷问：围绕会改变建模路线的分叉点建立假设、指标、候选模型、验证链和淘汰条件。优先问数据口径、目标函数、关键约束或风险偏好，不问命名、格式和可后置的小选择。
3. 归谬法极限测试：只对已成形的候选路线检查极端输入、边界条件、相互矛盾的假设、不可辨识性和可能导致荒谬结论的情形；路线尚未成形时不得提前使用。

### 提问纪律

- `question_budget` 是最多问题数，不是配额；没有会改变路线的关键问题时可以一个也不问。每轮只问一个最重要的问题，答案不能改变候选路线、约束、验证或交付的，不得询问。
- 提问前写出内部判据：“不同答案会导致哪两条不同路线？”无法给出两条实质不同的后续路线就直接采用有依据的默认值，并把假设记录在结果中。
- 使用宿主提供的结构化用户提问工具，给出 2–3 个互斥、可理解的选项，推荐项放在前面并说明影响，同时允许用户自由补充。不要连续抛出问卷，也不要重复卡片字段。
- 用户回答后先用一两句解释该答案改变了什么，再继续分析。达到预算、剩余问题影响很小或路线已足够决策完备时立即停止追问。

最终输出随 `objective` 和 `output_depth` 调整，但至少明确：一句话题意、事实/假设/未知量清单、逐问任务链、2–4 条候选路线及取舍、首选路线的输入—模型—求解—验证闭环、关键风险与下一步。只有 `output_depth=含压力测试` 或目标为“压力测试已有方案”时才输出完整归谬测试。该输出是可执行的建模简报，不修改项目文件、不虚构数据，也不替代官方题意。
