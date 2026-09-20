# AGENTS.md

本技能用于美赛 MCM/ICM 英语赛道。执行时的硬要求：

1. 用户手动调用本技能后，按 step0 到 step5 连续推进，不中途等待确认。
2. 第一条项目命令必须是 `run_stage_gate.py --init`，此后只用 `--stage stepN`；前序未通过不得进入下一阶段。
3. 论文交付物全英文：main.tex、图表、图注、坐标轴、图例、附录都不得出现中文字符，也不得加载中文宏包。
4. step2 就要完成逐问图型分配并写入 figures/manifest.json；step3 逐图调用 `choose_chart_family(..., used_families=...)`，保证跨问家族不重复，热图与柱图全文各最多 1 张。
5. 页数、Summary Sheet、章节白名单、加粗、文风、附录代码、三轮自查都按 references/ 下的契约执行。
6. 最终交付前运行 `verify_delivery.py`，只有 ok 为 true 才能声称完成。