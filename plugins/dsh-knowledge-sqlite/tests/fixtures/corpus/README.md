# 测试语料 fixture（hermetic）

本目录是实验语料的**逐字拷贝**（verbatim copy），供单元测试与本地冒烟独立运行
（不依赖仓库外的 `research/` 目录，CI 可跑）。

- 上游：`<workspace>/research/memory-knowledge-seam/experiments/memory-experiment/`
  （RESULTS-v3 基准实验语料：m1-m12 富化 + n1-n10 提炼 + 500 条 DSH 仓库文档段落干扰项）
- 覆盖：`all-memories.json` / `enriched.json` / `expanded.json` / `distractors.json` /
  `human-queries.json`（20 条真实用户消息，17 有目标 + 3 none）/ `human-expanded.json`
  （human 查询集离线 reasoner variants，C 臂诊断用，0.1.4 起）/ `data.mjs`（hard 查询集）

## 重新同步（语料更新后）

```sh
SRC=<workspace>/research/memory-knowledge-seam/experiments/memory-experiment
cp $SRC/all-memories.json $SRC/enriched.json $SRC/expanded.json \
   $SRC/distractors.json $SRC/human-queries.json $SRC/human-expanded.json $SRC/data.mjs .
```

同步后必须更新 `tests/service.spec.ts` 与 `test-smoke.mjs` 中断言值
（hard 确定性臂 A 7% / C 21% / D 50%、human A 65%、human C 71%）。
`human-expanded.json` 为 LLM 生成物（抽样有方差，见 EXPERIMENTS §7）：更换时需记录批次。
