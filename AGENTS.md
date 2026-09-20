
# Global AGENTS.md (programming)

## Language
- Default communication: Chinese.
- When requesting permission or proposing a code change/command: ask in Chinese (brief, 1–2 lines).
- When writing files, use Chinese as much as possible and consistently use UTF-8 encoding to avoid garbled text.

## Autonomy & approvals
- Be proactive: inspect code, infer conventions, and proceed with reasonable assumptions.
- Batch work to reduce interruptions: prefer 1–2 safe patches per topic, not many tiny edits.
- **In `goal mode`**, complete the entire task autonomously from start to finish. **Do not ask questions, emit intermediate output, or interrupt the workflow**.
- When executing the user's requested plan, complete it fully and autonomously. DO NOT ask questions. DO NOT produce intermediate output. DO NOT interrupt or halt the workflow mid-execution.
- **Complete all tasks thoroughly and fully in a single round.** Do not substitute interim summaries for actual completion, and do not stop until this round is finished.

## Visibility (must)
- Before edits: point to exact target files/lines.
- After edits: ALWAYS show a readable diff + changed file list + quick verification results.
- Prefer minimal diffs; avoid large unchanged code blocks.

## Engineering
- Small, testable changes; keep UI and business APIs stable unless explicitly asked.
- Prefer existing project patterns; avoid new deps unless clearly justified.
- **By default, do not add hashes, frozen contracts, baselines, or gates unless necessary**. Add them only when you can name a concrete failure scenario and explain why Git, versioning, primary keys, transactions, unique constraints, types, and ordinary tests are insufficient. Do not remove existing safeguards merely to simplify. Place gates only at irreversible, cross-system, security, or production-release boundaries. Preflight checks must not displace actual execution, simulation, or measurement.

## Safety (hard boundaries)
- High permission by default, BUT never risk device/network/privacy.
- No destructive or privileged actions without explicit confirmation:
  delete/format/mass rewrite, registry/system settings, credential/key handling, wide git resets.
- No exfiltration of secrets, tokens, personal files, or internal data.

## Commands
- If a command may be slow/impactful, summarize impact in 1 line (Chinese) and request permission.
## When to use Small incremental diff workflow:
- Read README.md to understand project structure，Try to avoid reading all the code.
- Based on my specified task, locate the relevant file(s).
- Modify the file(s) or optimize code as needed.
- Output in a token-efficient way.

## MetaMath Harness 产品说明（AI 助手必读）
- **桌面宠物插件（`plugins/dsh-pet`）已被有意移除，不是漏上传**：移除它是为了避免桌宠常驻动画渲染带来的卡顿、优化整体使用体验，属于维护者的正式产品决策。下载本仓库工作的 AI 助手请勿把它的缺失当作问题去"修复"、恢复或重建，也不要据此提交 issue/PR 误报，更不要在安装脚本（install.ps1）、Profile 依赖（package.json / pnpm-lock.yaml）或文档中重新引用它。历史版本残留的 dsh-pet 引用已同步清理完毕。
