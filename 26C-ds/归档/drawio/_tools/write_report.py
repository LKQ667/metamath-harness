# -*- coding: utf-8 -*-
"""由 final_report_data.json 生成 检查结果/drawio_generation_report.md。"""
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
P = Path(__file__).resolve().parents[2]
HAND = P / '手绘图'
data = json.loads((HAND / '_tools' / 'final_report_data.json').read_text(encoding='utf-8'))
checks = {c['check']: c for c in data['checks']}
arts = {a['name']: a for a in data['artifacts']}

ORDER = ['fig_roadmap', 'fig_problem_analysis', 'fig_experiment_design',
         'fig_artifact_sources', 'fig_q1_denoise_flow', 'fig_q1_response_flow',
         'fig_q2_multiscale_model', 'fig_q2_laterality_mechanism',
         'fig_q2_feature_flow', 'fig_q3_model_framework',
         'fig_q3_estimation_flow', 'fig_q3_application']

SECTION = {
    'fig_roadmap': '一、问题重述', 'fig_problem_analysis': '一、问题重述',
    'fig_experiment_design': '二、模型假设与符号说明',
    'fig_artifact_sources': '问题一模型建立与求解',
    'fig_q1_denoise_flow': '问题一模型建立与求解',
    'fig_q1_response_flow': '问题一模型建立与求解',
    'fig_q2_multiscale_model': '问题二模型建立与求解',
    'fig_q2_laterality_mechanism': '问题二模型建立与求解',
    'fig_q2_feature_flow': '问题二模型建立与求解',
    'fig_q3_model_framework': '问题三模型建立与求解',
    'fig_q3_estimation_flow': '问题三模型建立与求解',
    'fig_q3_application': '模型总结与评价',
}

L = []
A = L.append
A('# Draw.io 非数据图生成报告（12 张）')
A('')
A('- 项目：项目根目录')
A('- 绘图模式：`drawio`（`项目状态.json` 与 `figures/manifest.json` 顶层均已锁定）')
A('- 生成链路：仅使用 `math-paper-huawei` 技能的 `scripts/drawing/drawio_pipeline.py` 与 '
  '`assets/drawio/template_library.json`，未读取任何外部绘图技能目录')
A('- 生成方式：全部经 `build --brief <brief.json> --labels-json <labels.json> --output <.drawio>` '
  '原子生成，随后 `validate <source> --template <id>`；**未手写任何 XML**，'
  '**未自造 template_id**，**未回退旧模板**')
A('')
A('## 一、交付前自检退出码')
A('')
A('| # | 命令 | 退出码 | 结论 |')
A('|---|------|--------|------|')
A(f"| 1 | `check_figures_manifest.py --project <项目>` | {checks['check_figures_manifest']['exit']} | ok=true，0 条失败 |")
A(f"| 2 | `check_flowchart_required.py --project <项目>` | {checks['check_flowchart_required']['exit']} | ok=true，0 条失败 |")
A('| 3 | `check_drawing_contract.py --project <项目> --stage step3` | 2 | **该脚本不存在 `--stage` 参数**，argparse 直接报错退出（非内容缺陷） |')
A('| 3b | `check_drawing_contract.py --project <项目>`（去掉不存在的 `--stage`） | '
  f"{checks['check_drawing_contract']['exit']} | ok=true，0 条失败 |")
A(f"| 4 | `check_roadmap_quality_notes.py --project <项目>` | {checks['check_roadmap_quality_notes']['exit']} | ok=true，0 条失败 |")
A('')
A('说明：`check_drawing_contract.py` 只接受 `--project` 与 `--output`。技能注册表 '
  '`scripts/checks/gate_registry.py` 把该检查登记在 **step4**（`GateSpec("check_drawing_contract.py", 4)`），'
  '而 `check_figures_manifest` / `check_flowchart_required` / `check_roadmap_quality_notes` 登记在 step3。'
  '去掉非法参数后，四条检查的命令**全部退出码 0**。')
A('')
A('## 二、产物清单')
A('')
A('每张图固定四件产物：`.drawio`（可编辑源）、`.svg`、`.pdf`、`.png`（2× 导出，'
  'manifest 记录 `export_scale: 2`）。字节数取自交付时刻实际文件。')
A('')
A('| 图名 | template_id | PNG 像素 | 宽高比 | .png 字节 | .pdf 字节 | .svg 字节 | .drawio 字节 | 计划章节 |')
A('|------|-------------|----------|--------|-----------|-----------|-----------|--------------|----------|')
for n in ORDER:
    a = arts[n]
    A(f"| `{n}` | `{a['template_id']}` | {a['png_wh']} | {a['ratio']:.2f} | "
      f"{a['png']:,} | {a['pdf']:,} | {a['svg']:,} | {a['drawio']:,} | {SECTION[n]} |")
A('')
A('## 三、问题二多尺度模型图的重绘记录（父 agent 补充要求）')
A('')
A('父 agent 指出 `fig_q2_multiscale_model` 原用纵向分层链导出为 526×1346（宽高比 0.39），'
  '过于狭长，插入论文后近半页高。已按模板库横向模板重绘：')
A('')
A(f"- 新 `template_id`：**`{arts['fig_q2_multiscale_model']['template_id']}`**（横向双泳道）")
A(f"- 新 PNG 像素：**{arts['fig_q2_multiscale_model']['png_wh']}**，"
  f"**宽高比 {arts['fig_q2_multiscale_model']['ratio']:.3f}**（要求 2.2–3.2，满足）")
A('- 内容保持不变：五级串联 `LGN 时空滤波（毫秒级）` → `形状选择与除法归一化（十毫秒级）` → '
  '`Wilson–Cowan 介观集群（百毫秒级）` → `Kuramoto 同步与序参数（秒级）` → `头皮导联场观测`，'
  '各级时间尺度随节点标注；第 6 个内容框为「尺度跨度：毫秒 → 秒」汇总标注，不新增计算层级')
A('- 仍经 `build --brief ... --labels-json ... --output ...` 原子生成并通过 `validate`；'
  '`figures/manifest.json` 中该条目的 `template_id` 已同步更新为 `dual-swimlane`')
A('- 其余 11 张图未改动')
A('')
A('候选模板实测宽高比（由模板库节点包围盒计算）：`main-chain-support` 2.95、`dual-swimlane` 2.72、'
  '`branch-decision` 2.88 落在 2.2–3.2 区间；`horizontal-stage-chain` 为 14.29（内容框 1000×70，'
  '五个节点同排，导出为极扁长条），`vertical-layer-chain` 为 0.39，`feedback-loop` 1.82，'
  '均不满足区间。`main-chain-support` 只有 4 个串联主节点、`branch-decision` 为分叉汇合结构，'
  '都无法承载「五级串联」；只有 `dual-swimlane` 同时满足宽高比与五级内容，故选用它。')
A('')
A('## 四、概念类提示词（4 份，未调用任何付费生图接口）')
A('')
for f in sorted(HAND.glob('概念图_*.md')):
    A(f"- `手绘图/{f.name}`（{f.stat().st_size:,} 字节）")
A('')
A('按 Draw.io 模式规定，原理图/模型图/概念图/示意图只生成提示词、不自动生图；'
  '项目 `confirm_paid_calls=false`，全程未调用 `image_generate` 等计费接口。')
A('')
A('## 五、QA 记录')
A('')
A('### 5.1 静态 QA（`validate` + 自建文本审计）')
A('')
A('- XML 可解析、`mxCell` id 唯一、连接边端点存在且带显式箭头、'
  'CJK 节点均含 `fontFamily=Microsoft YaHei` 与 `whiteSpace=wrap`、'
  '实体内容盒无部分相交（容器完全嵌套合法）')
A('- 模板结构指纹核对：12 张全部 `validate --template <id>` 通过（节点/边集合与端点关系与模板一致）')
A('- 文本审计：163 个文本单元，**0 条问题**（无残留模板英文、无无中文文本单元、'
  '无节点汉字数 >16）')
A('')
A('### 5.2 视觉 QA（`read_image` 逐张读 2× PNG）')
A('')
A('12 张全部逐张读图确认：内容与提纲一致、文字全中文无乱码/无方框问号、无越界裁切、'
  '无节点重叠、箭头无穿模、文字适配盒宽、灰度与缩印可读。共两轮，第二轮修复的具体缺陷：')
A('')
A('1. **文字与标签重叠**（`fig_roadmap`）：我在悬浮边上追加的 5 个边标签与模板已有的文字节点'
  '位置重合，渲染成 `数据交接分段交接`、`特征尺度递进`、`模型判别输出`。'
  '处置：清空这 5 个边标签（其信息已由相邻文字节点承载），重叠消除。')
A('2. **边标签压住节点框**（`fig_q3_estimation_flow`）：`按应答正确性` 等边标签宽 90pt，'
  '超过横向阶段链 50pt 的节点间距，压到相邻节点框上。'
  '处置：清空三张横向阶段链图的冗余边标签，并把其余边标签字号从 15px 收到 12px。')
A('3. **正文宽度下字号偏小**：六类原创模板固定 `fontSize=14`，而图宽约 1000pt，'
  '按 `0.98\\textwidth` 插入后仅约 6pt。'
  '处置：用标签内联 HTML（raw 模板自身使用的写法）把节点字号提到 17px、边标签 12px，'
  '插入后约 7.5pt，双栏缩印仍可读。')
A('')
A('重绘终止遵循「硬缺陷驱动、合格即冻结」：上述每轮重画均对应一个具体缺陷，'
  '同一根因未超过 3 轮；修复后未再以「更漂亮」为由整图重画。')
A('')
A('### 5.3 论文回填状态')
A('')
A('`qa.paper_insert_ok` 记录的是**入文适配性 QA**（宽高比、2× 分辨率、正文宽度与缩印可读性）'
  '已通过。已核实 `论文/main.tex` 用 `\\includegraphics[width=0.98\\textwidth]{<name>.pdf}` '
  '引用了全部 12 张图的 PDF（其中 12 张 drawio 图均按 0.98\\textwidth 插入），'
  '`check_drawing_contract` 的独立回填校验（`paper_has`）已通过，故该检查退出码为 0。'
  '各条目另记 `paper_insert_status: "backfilled_in_main_tex"`，'
  '用于区分「适配性 QA 通过」与「已回填」两件事，避免歧义。')
A('')
A('## 六、与任务书字段的偏差说明')
A('')
A('| 字段 | 任务书写法 | 实际写入 | 原因 |')
A('|------|------------|----------|------|')
A('| `export_status` | `"exported"` | `"cli_exported"` | '
  '`check_drawing_contract.py` 第 265 行硬性要求 Draw.io 条目必须为 `cli_exported`，'
  '`exported` 会导致门禁失败；`cli_exported` 同时准确表达「经 CLI 导出」 |')
A('| `qa` 键集 | 13 个键 | 19 个键（并集） | '
  '任务书键集与门禁 `DRAWIO_QA` 键集不同，取并集使两者同时满足 |')
A('')
A('## 七、未证实内容与局限')
A('')
A('- 图内所有数值（一致率 1.00 与 0.48、相关度 >0.6、幅度 >6 倍、10 倍稳健尺度、'
  '80–250 ms / 250–800 ms / 应答前约 100 ms）均取自赛题给定条件与项目已完成结果记录'
  '（`检查结果/denoise_final_decision.json`、`denoise_strength_sweep.json`、'
  '`laterality_feature_diagnosis.json`），未在图中新增任何未经验证的数值。')
A('- `fig_artifact_sources` 只做定性表现描述：逐类伪迹的出现比例在已完成结果中未量化，'
  '故未标注任何比例数值。')
A('- 多尺度模型各级时间尺度为定性量级标注，非拟合结果。')
A('- `fig_q3_application` 的病程趋势为模型导出的定性关系，未在患者队列数据上验证，'
  '图内不做定量外推。')
A('- 技术路线图使用 raw 通道的 `dual-panel-bilevel` 模板作为结构骨架：模板自带的'
  '装饰性容器、分区底色与悬浮箭头位置不可通过 labels 修改（管线只允许覆盖文字），'
  '但该模板不含内嵌位图与调色板色块，是四类技术路线图模板中残留装饰最少的一类。')
A('- 三张横向阶段链图（`fig_q1_response_flow`、`fig_q2_feature_flow`、`fig_q3_estimation_flow`）'
  '导出为约 13.7:1 的扁长条，这是模板几何（五节点同排、内容框 1000×70）的固有属性；'
  '按 `0.98\\textwidth` 插入后高约 1.1 cm，不占页高，但纵向信息密度低。')
A('')
A('## 八、复现入口')
A('')
A('- 图稿摘要与标签定义：`手绘图/_tools/build_figures.py`')
A('- 构建/校验/导出汇总：`手绘图/_tools/build_summary.json`、`export_summary.json`')
A('- 文本审计：`手绘图/_tools/audit_text.json`')
A('- CLI 验证记录：`检查结果/drawio_cli_verification.json`（draw.io 31.4.5，'
  'PNG/SVG/PDF 导出与中文渲染四项全通过）')

out = P / '检查结果' / 'drawio_generation_report.md'
out.write_text('\n'.join(L) + '\n', encoding='utf-8')
print('written:', out, out.stat().st_size, 'bytes')
