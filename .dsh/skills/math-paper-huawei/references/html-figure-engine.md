# HTML 矢量成图引擎手册（math-paper-huawei 内置，整体并入自 html-paper-figure）

本文件是 `html-paper-figure`（MetaMath Harness/DSH 适配版）技能手册的**整体并入版**，服务于 math-paper-huawei 的 `drawing_mode=HTML矢量成图`（内部模式值 `html`）。引擎的出图工具、KaTeX 素材与兜底模板已随本技能内置在 `<技能目录>/assets/html-figure/`（`templates/`、`tools/`），**运行时只读取本技能内置资源，禁止读取外部 `html-paper-figure` 目录**——把 math-paper-huawei 放到任何 agent、任何电脑上都可独立执行。

用 HTML+CSS 生成论文非数据类示意图：只处理流程/路线类示意图（技术路线图、问题分析流程图、各问求解流程图），自动生成范围与 Draw.io 模式完全一致；概念类图（原理图/模型图/概念图/示意图）在本模式下同样只保留 2–4 份提示词、不生图。数据图（matplotlib/seaborn）始终沿用本技能既有 Python 链路，不进本引擎。

**HTML 相对 DrawIO 的核心优势**：用 flex/grid 自动布局，不写绝对坐标 → 天然免疫节点重叠/坐标错位/连线穿越。因此本引擎**不需要** drawio 的坐标结构自检（drawio_check.py），改用 HTML/PDF 专属质检（`html_pdf_check.py` + `--geom-check`）。

## ⚠ 运行环境约定

- **命令一律经运行时的 shell 工具执行**（DSH 下为 `pwsh` 工具）：每次调用都是全新进程，**变量不跨调用保留**，工作目录用 `workdir` 参数指定。本文 bash/PowerShell 块仅作语义参考，执行时按当前运行时语义落地（`ls figures/*.pdf | wc -l` → `(Get-ChildItem 手绘图\*.pdf).Count`；`grep -c` → `Select-String | Measure-Object`；临时文件写工作区 `_tmp\`，不写 `/tmp/`）。
- **视觉自检优先用运行时原生视觉能力**（DSH 下为 `read_image` 直接看渲染出的 PNG，或 `vision_analyze` 让视觉模型审图；其他运行时用其等价图像查看能力）。PDF→PNG 用 PyMuPDF（`fitz`）。⛔ 视觉能力明确返回"无法查看图片"时按 skipped 处理，禁止凭文件名/尺寸/上下文猜测图面内容。
- 下文 `$CAPTURE` / `$HTMLCHECK` / `$TPL_DIR` 等是**语义简写**，指《工具路径解析》一节定位出的完整路径；由于 shell 变量不跨调用，每次实际执行前先在该次调用里重新赋值（或直接写完整路径）。
- 本引擎依赖事实：`python` 可用（⛔ 不用 `python3`，Windows 下会触发 Microsoft Store 存根）；PyMuPDF(fitz) 用于 PDF→PNG 与尺寸读取；出图依赖 **Electron**（`screenshot_capture.py` 自动定位：环境变量 `MH_ELECTRON_EXE` → PATH 上的 `electron` → 回退 `npx --yes electron`，首次自动下载到 npm 缓存后秒启）。**Electron/node 完全不可用时本引擎无法出图**，必须按《做题前选路》退回 Draw.io 模式并在 manifest 记录原因，不得伪造产物。

## ⚡ 快速模式检测（开头先定一次）

**FAST_MODE 默认 0**（质量优先）。当用户在当前对话明确说"快速模式/赶时间/跳过视觉自检"时记 FAST_MODE=1，并在 Step 5 / Step 7 一致按 1 处理（shell 变量不跨调用，各步骤就地重判一次，不依赖文件探测）。

**若 `FAST_MODE=1`（速度优先）：** 仍按图表清单产出所有图（一张不漏、能出 PDF、过 html_pdf_check、**过 Step 4.5 元素级几何自检**），但**跳过** vision 视觉自检的多轮修复循环——生成即用，仅当 html_pdf_check FAIL 或明显空图时才补。**若 `FAST_MODE=0`（默认）：** 视觉自检修复循环照常执行。⛔ **几何自检（Step 4.5）任何模式都跑**：它快（纯几何、几十毫秒）、且能挡"文字被裁/越界/重叠"这类真翻车，不算 vision 加分项。

**重画终止条件（与全链路一致）：** `html_pdf_check` 与 `--geom-check` 全部通过、且 Step 5 视觉审查没有硬缺陷（溢出、截断、重叠、越界、错位、乱码、箭头穿模等）时，立即把该图标记 `paper_ready: true`、`needs_visual_review: false` 并冻结，不得因为"也许还能更漂亮""再优化一下"继续重画。每轮修复必须对应一个已列明的具体缺陷，第 3 轮用完后按 unresolved 记账继续，不进入无界循环；已合格版本不被 QA 更差的新候选覆盖。

## Constants

- **FIG_DIR = `手绘图/`**（math-paper-huawei 非数据绘图统一产物目录；中间产物 `.html`、最终产物 `.pdf`、交付 PNG 同名同目录）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求，最高优先级。

## ⛔ 工具路径解析（每次会话开头先定位，实际执行时在各次 shell 调用里重新赋值）

把 math-paper-huawei 的 `SKILL.md` 所在目录记为 `<技能目录>`（与 SKILL.md《交付门禁》一节同一记法）。本引擎全部工具随技能内置，解析防御式进行，找不到再报错：

```powershell
# ⛔ 这台机器必须用 python，不能用 python3（python3 触发 Microsoft Store 存根，exit 49）
$PYTHON = 'python'

# 技能目录（math-paper-huawei 的 SKILL.md 所在目录；按当前会话实际位置解析，禁止回退历史固定盘符）
$SKILL_DIR = '<技能目录>'

# 模板目录（仅极端兜底参考，正常流程不读）
$TPL_DIR = Join-Path $SKILL_DIR 'assets\html-figure\templates'
"模板目录 TPL_DIR=$TPL_DIR"

# 出图工具（screenshot_capture.py：包装器，内部自动调 Electron + 同目录 capture.js + katex-assets/）
$CAPTURE = Join-Path $SKILL_DIR 'assets\html-figure\tools\screenshot_capture.py'
"出图工具 CAPTURE=$CAPTURE"

# HTML/PDF 质检脚本
$HTMLCHECK = Join-Path $SKILL_DIR 'assets\html-figure\tools\html_pdf_check.py'
"质检脚本 HTMLCHECK=$HTMLCHECK"

# include 尺寸规整脚本（论文回填后按真实长宽比自动纠 width）
$INCSIZE = Join-Path $SKILL_DIR 'assets\html-figure\tools\fig_include_size.py'
"尺寸规整 INCSIZE=$INCSIZE"

# 视觉自检：运行时原生视觉能力（DSH：read_image / vision_analyze），不依赖外部脚本。

# ===== TikZ 依赖（⛔ 本技能锁定模式契约下默认关闭，见 Step 5.5 顶部说明；此处仅保留探测）=====
$XELATEX = (Get-Command xelatex -ErrorAction SilentlyContinue).Source
"TikZ 编译器 XELATEX=$(if ($XELATEX) { $XELATEX } else { '（不可用）' })"
```

出图前可先跑 `python $CAPTURE --check` 预先探测 Electron（退出码 0=可用 / 2=不可用）。

## ⛔⛔⛔ Output Contract（最高优先级）

**HTML 模式产物契约与 Draw.io 模式对齐（同一 `手绘图/`、同一 `figures/manifest.json`、同一论文回填口径），由项目门禁 `check_drawing_contract.py` 代行对账：**

- 自动生成范围与 Draw.io 模式一致：**技术路线图（至少 1 张，step4 前硬门禁）**、问题分析流程图、各问求解流程图；概念类图（原理/模型/概念/示意图）只保留 2–4 份提示词，**不生图**。
- 固定产物三件套，同一 `<name>` 同目录同名：
  - `手绘图/<name>.html` — 可追溯源（自包含单文件，flex/grid 相对布局）；
  - `手绘图/<name>.pdf` — Electron printToPDF 矢量单页无白边终稿，论文 `\includegraphics` 直接引用；
  - `手绘图/<name>.png` — 交付 PNG（以 192/72 倍率≈2× 从 PDF 渲染导出，供缩印审查与交付评分卡）。
- `<name>` 命名与 Draw.io 模式对齐（如 `技术路线图`、`问题分析流程图`、`Q1求解流程图`，或 `fig_roadmap`/`fig_flow_q1` 语义命名，全篇统一；避免空格）。
- ⛔ **图内绝不放标题**：标题一律由 LaTeX `\caption{}` 管理（避免标题重复、字体不一致）。
- ✅ **流程/算法图里的公式可直接写在 HTML 里**：节点文字内用 `\( ... \)`（行内）或 `\[ ... \]`（独立行）写 LaTeX，出图时命令带 `--render-math`（见 Step 3），截图管线会注入 KaTeX 把它们渲染成真公式（矢量、可放大不糊）。
- ⛔ **TikZ 精密几何图在本技能锁定模式契约下默认关闭**（Step 5.5 仅作能力保留）：原理/模型/概念/几何示意图一律按锁定模式契约保留提示词，不得作为 manifest 条目自动生图。
- manifest 条目（`figures/manifest.json` 的 `items`）每个非数据绘图条目提供统一九字段：`generator: "html"`、`template_id`（非空，记录所用骨架/范式，如 `skeleton_swimlane`；**技术路线图必须取自骨架池四类** `skeleton_swimlane`/`skeleton_spine`/`skeleton_twocolumn`/`skeleton_layered`）、`source`（`手绘图/<name>.html`）、`exports`（含 `.pdf` 与 `.png`）、`prompt_source`（该图图稿摘要：与 Draw.io 模式同规格的 brief JSON 或设计说明 md）、`paper_ready: true`、`export_status: "electron_printed"`、`needs_visual_review: false`（完成视觉复核后）、`qa`（对象，键集见门禁：`html_pdf_check_ok`、`geom_check_ok`、`content_ok`、`cn_text_ok`、`layout_ok`、`text_fit_ok`、`grayscale_ok`、`single_column_ok`、`double_column_ok`、`paper_insert_ok` 全部 true）。
- ⛔ 结束前必须自检：`手绘图/` 每个流程类 `<name>` 三件套齐全、manifest 条目九字段完整、`论文/main.tex` 已用 `\includegraphics` 插入每张 PDF。缺任一项不得宣称完成；这些同时也是项目阶段门禁的硬检查项。

## Workflow

### Step 0: 恢复检查（断线重跑必读）

⛔ 本步骤可能因断线/手动重跑被多次启动。每次启动前**必须**先扫描已有产物：

```powershell
Write-Output "=== 工作区扫描 ==="
$HAS_HTML = (Get-ChildItem 手绘图\*.html -ErrorAction SilentlyContinue).Count
$HAS_PDF  = (Get-ChildItem 手绘图\*.pdf  -ErrorAction SilentlyContinue).Count
$HAS_PNG  = (Get-ChildItem 手绘图\*.png  -ErrorAction SilentlyContinue).Count
Write-Output "  *.html: $HAS_HTML, *.pdf: $HAS_PDF, *.png: $HAS_PNG"
Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue |
    Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
```

| 状态 | 行动 |
|---|---|
| 图表清单要求的图都已生成（.html + .pdf + .png 三件套且过 html_pdf_check 与几何自检） | **跳到 Step 6（论文回填核对）**，验证通过即完成 |
| 部分已生成 | **只生成缺失的**（已有的不重画） |
| 啥都没有 | 从 Step 1 开始 |

⛔ **铁律**：已有的 `手绘图/*.html` / `*.pdf` / `*.png` 不要重写。

### Step 1: 读规划 + 确定要画哪些图 + 算风格种子

1. **确定图表清单与语言**（math-paper-huawei 口径，替代上游的 PAPER_PLAN/PROBLEM_ANALYSIS 对账）：

```powershell
# 语言锁定：与项目状态 competition_language 一致（中文赛项图内全中文，英文赛项全英文）
$STATE = Get-Content 项目状态.json -Raw | ConvertFrom-Json
$FIG_LANG = if ($STATE.competition_language -eq '英文') { 'en' } else { 'zh' }
Write-Output "图内文字语言: $FIG_LANG"

Write-Output "=== HTML 模式图表清单（技术路线图必画，其余按需） ==="
# 清单来源：figures/manifest.json 规划 + 各问 Q*/README.md、result.md 中的建模与求解链路。
# 至少 1 张技术路线图（技术路线图硬门禁）；问题分析流程图、各问求解流程图按题目复杂度列全。
```

2. **⛔ 输出 HTML PLAN CHECKLIST（后续步骤对照用，清单就是合同）：**

- **技术路线图 `fig_roadmap`（或中文命名）至少 1 张，必画。**
- 问题分析流程图、各问求解流程图按需列出；**没有列进清单的就一张都不要画**，自作主张补齐属于违规超产。
- 概念类图不出现在本清单（本模式只保留提示词）。

```
HTML PLAN CHECKLIST:
[ ] 1. fig_roadmap   — 技术路线图 (骨架池按 SKELETON 种子选择, HTML)
[ ] 2. fig_flow_q1   — 问题一求解流程图 (HTML；公式写 \(...\)，出图加 --render-math)
[ ] 3. fig_analysis  — 问题分析流程图 (HTML)
Total: N 张
```

3. **⛔ 计算「确定性风格种子」**（不再从预设里挑主题）。风格种子由**项目根目录名**（=项目 ID）确定性哈希得来，保证：**同一篇论文所有图共用同一种子 → 视觉统一；不同论文/不同项目种子不同 → 风格各异；断线重跑种子不变 → 可复现**。

```powershell
# 风格种子 = 项目根目录名的确定性哈希（python zlib.crc32，跨次运行稳定可复现）
$WFID = Split-Path -Leaf (Get-Location)
$SEED = [long](python -c 'import sys,zlib;print(zlib.crc32(sys.argv[1].encode()))' "$WFID")
$H0 = $SEED % 360
# 回避刺眼黄绿[50,70) 与 高纯红[330,360)∪[0,10)
if (($H0 -ge 50 -and $H0 -lt 70) -or $H0 -ge 330 -or $H0 -lt 10) { $H0 = ($H0 + 40) % 360 }
$TONE = $SEED % 3   # 造型档(均为黑白基调+H0强调): 0=纯黑白线稿 1=彩边白卡 2=灰阶分区+单焦点
# ⛔ 结构旋钮：从 SEED 不同位段派生(互相独立、不跟 H0/TONE 绑死)，全是"黑白造型"变化、不加颜色。
$RADIUS   = ([int][math]::Floor($SEED / 7))  % 4     # 圆角: 0=直角 1=微圆(4px) 2=圆角(10px) 3=胶囊(999px)
$ARROW    = ([int][math]::Floor($SEED / 11)) % 4     # 连线: 0=细实箭头 1=粗实箭头 2=点线箭头 3=chevron(›)分隔
$NODEACC  = ([int][math]::Floor($SEED / 13)) % 3     # 焦点/类型节点的强调方式: 0=纯描边 1=左竖条 2=顶横条
$SECT     = ([int][math]::Floor($SEED / 17)) % 3     # 分区/分组框法: 0=无框(留白分组) 1=细虚线框 2=左侧竖标签条
# ⛔ LAYOUT：布局拓扑选择种子。A 节某逻辑类型列了【多个等价范式】时按 "LAYOUT % 候选数" 确定性选一个。
$LAYOUT   = ([int][math]::Floor($SEED / 19)) % 6
# ⛔ SKELETON：技术路线图/求解流程图的【骨架池选择】(0横向泳道 1主干侧挂 2左右双栏 3分层堆叠)。见文末《骨架池》。
$SKELETON = ([int][math]::Floor($SEED / 29)) % 4
# ⛔ STYLE_FAMILY：风格族（最顶层维度）。0=A朴素竞赛风 1=B现代精致风 2=C纯黑白线稿（硬约束见文末《G 风格族》）。
$STYLE_FAMILY = 2   # ⛔ 默认纯黑白 C：最不"AI感"、最像传统竞赛/数模论文、印刷友好。布局差异由 SKELETON/LAYOUT 承担。
# ⛔ 用户手选覆盖（可选）：项目 AGENT.md 里写了 MH_DIAGRAM_STYLE=N（0/1/2）就用它覆盖默认。
$_FORCED_FAM = ''
if (Test-Path AGENT.md) {
    $_m = Select-String -Path AGENT.md -Pattern 'MH_DIAGRAM_STYLE=([0-2])' | Select-Object -First 1
    if ($_m) { $_FORCED_FAM = $_m.Matches[0].Groups[1].Value }
}
if ($_FORCED_FAM -ne '') { $STYLE_FAMILY = [int]$_FORCED_FAM }
$_FAM_NAME = @{ 0 = 'A 朴素竞赛风'; 1 = 'B 现代精致风'; 2 = 'C 纯黑白线稿' }[$STYLE_FAMILY]
Write-Output "🎨 风格种子 SEED=$SEED  STYLE_FAMILY=$STYLE_FAMILY（$_FAM_NAME）  SKELETON=$SKELETON  H0=$H0°  TONE=$TONE  RADIUS=$RADIUS  ARROW=$ARROW  NODEACC=$NODEACC  SECT=$SECT  LAYOUT=$LAYOUT（全篇共用）"
```

- **H0（强调色相）** 是全篇**强调色**的种子（节点主体是黑白灰，H0 只染焦点/语义连线/类型边框等 ≤15% 的部分），Step 2 按《设计规范 B 节》从它 HSL 推导强调色 + 灰阶色板。
- **TONE（造型基调）** 决定全篇统一的造型档次（见《设计规范 D 节》）。
- **RADIUS/ARROW/NODEACC/SECT（造型旋钮）** 决定圆角、连线样式、节点强调条、分区框法——**全是黑白造型变化、不加任何颜色**，按《设计规范 F 节》落到 CSS。它们把**皮肤**拉开差异。**全篇所有图共用同一组值。**
- **LAYOUT（拓扑旋钮）** 把差异从"皮肤"升到"骨架"：当某图的逻辑在 A 节表里有**多个等价范式**时，用 `LAYOUT` 确定性选一个（选编号 `= LAYOUT % 候选数` 的那个），使同类题的不同用户**宏观骨架朝向也不同**。⛔ 仅在**逻辑等价**范式间选，绝不为套种子而失真；逻辑只有唯一贴合范式的不参与轮选。**全篇共用同一值。**
- **STYLE_FAMILY（风格族，最顶层）** 先定**三大类观感**（A 朴素竞赛风 / B 现代精致风 / C 纯黑白线稿），族内硬约束见文末《G 风格族》（族说了算，凌驾于同名旋钮）；H0/LAYOUT/ARROW 仍在族内照常随机（C 族强制零彩色，不用 H0）。
- **可选的学科微调**：若题目明显属某学科（能源/经济/计算机…），允许把 H0 吸附到规范 B.1 列的友好色带；否则直接用种子值。**吸附也要全篇一致。**

⛔ 记下 `STYLE_FAMILY`/`H0`/`TONE`/`RADIUS`/`ARROW`/`NODEACC`/`SECT`/`LAYOUT`，Step 2 每张图都按同一组值设计——**禁止逐图换、禁止随机数/时间戳**。

### Step 2: 逐张自主设计并生成 HTML（读设计规范 → 按逻辑与种子设计 → 直接 write 工具写出）

⛔ **一次只画一张 → 转 PDF → 质检 → 过了再画下一张**（与 Draw.io 模式"逐张画逐张检"一致，避免批量出错难定位）。

⛔ **不"选模板填字"。** 每张图**由你按下方《AI 自主生成 HTML 流程图设计规范》从零设计** HTML/CSS：结构服从该图的真实逻辑，配色/造型由 Step 1 的 `H0`/`TONE` 推导。这样同篇视觉统一、异篇风格各异、同篇内每张图因逻辑不同而结构不同。

**产物文件名契约**（Output Contract；`$TPL_DIR` 下 5 个 `.html` 仅极端兜底参考，正常流程不读模板、不复制模板）：

| 图的用途 | 产物文件名 |
|---|---|
| 技术路线图（阶段推进/时间轴） | `手绘图/fig_roadmap.html`（或中文命名） |
| 问题分析流程图 | `手绘图/fig_analysis.html` |
| 求解流程图（仅当清单里有） | `手绘图/fig_flow_q1.html` / `fig_flow_q2.html` … |

**对清单里每一张图，按顺序：**

1. **先读规范再动手**：通读本文件末尾《AI 自主生成 HTML 流程图设计规范》A–E 节。用一句话说清这张图的**逻辑流向**（如"q1 是线性四步预处理"、"q3 是带收敛判断的迭代循环"、"q5 是三模块并行汇合"），再按 A 节的「逻辑类型→等价范式」表定骨架：**先锁定逻辑贴合的那一类，若该类列了多个等价范式就按 `LAYOUT % 候选数` 确定性选一个**——**不同子问题逻辑不同，就该长得不同**。⛔ 同时守 **A.1**：节点填这道题**特有的**方法/模型/判据实体（不写"数据预处理/建立模型"这类通用空词），并把方法**真实存在**的非平凡结构（校验回调/假设分支/收敛回环/多方法比选）挖出来画上。⛔ 复杂范式照 **A.2 骨架库**搭 flex/grid，别退化成一根线；出图前对照 **D.1 高级感五条**逐条过。技术路线图/求解流程图骨架从《骨架池》按 `SKELETON` 选。
2. **先定风格族，再推导配色/造型**：⛔ **第一步先读文末《G 风格族》，按 `STYLE_FAMILY` 落定基线**——字体族、节点底色、圆角上限、阴影、副标题、分组框（直接照抄 G.1/G.2/G.4 的 `:root`+节点骨架）。**然后**按 B 节从 `H0` 用 HSL 推导强调色代入，按 D 节 `TONE` 在族允许范围内定层次。⛔ 族与旋钮冲突时**以族为准**。**全篇所有图共用同一 `STYLE_FAMILY`/`H0`/`TONE`。**
3. **直接用 write 工具写出 `手绘图/<name>.html`**（自包含单文件），务必满足：
   - ⛔ **满足规范 0 节全部硬约束**（根容器+html+body 全 `width:fit-content`；flex/grid 自动布局禁 absolute；单文件禁外链；图内无标题；单页、宽高比 ≤8:1；公式用 `\(...\)`/`\[...\]` 写进节点、出图加 `--render-math` 渲染）。
   - ⛔ **逻辑完美嵌入**：填项目真实的**方法名/步骤/模块/子问题**，不留占位文字（"核心模型""方法A"要换成论文实际模型名、算法名）。
   - ⛔ **图内文字语言 = `$FIG_LANG`**（与 `competition_language` 一致）。
4. **每张生成后立即验证文件存在**：
```powershell
if (Test-Path 手绘图\fig_roadmap.html) { Write-Output "✅ fig_roadmap.html created" } else { Write-Output "❌ MISSING" }
```

### Step 3: 转 PDF（Electron printToPDF，矢量单页无白边）

对刚生成的 HTML 转 PDF：

```powershell
# 无公式的图：
python $CAPTURE --file 手绘图\fig_roadmap.html --out 手绘图\fig_roadmap.pdf --format pdf 2>&1 | Select-Object -Last 8
if (Test-Path 手绘图\fig_roadmap.pdf) { Write-Output "✅ fig_roadmap.pdf 已生成" } else { Write-Output "❌ PDF 生成失败" }

# 含公式的图（节点里写了 \(...\)/\[...\]）：必须加 --render-math，KaTeX 才会渲染公式
python $CAPTURE --file 手绘图\fig_flow_q1.html --out 手绘图\fig_flow_q1.pdf --format pdf --render-math 2>&1 | Select-Object -Last 8
```

- `--format pdf`（或 out 以 .pdf 结尾）→ 量内容真实像素、页面设成刚好等于内容 → **单页、无白边、真矢量**（文字可选可搜、无限放大不糊），等效 drawio `--crop`。
- `--render-math` → 截图前注入 KaTeX 渲染 HTML 里的 `\(...\)`/`\[...\]`/`$$`（素材在同目录 `katex-assets/`）。**图里有公式就必须加**；没公式不用加（无害但多一步）。素材缺失时自动降级（图仍出、公式不渲染），不阻断。
- 若 `$CAPTURE` 定位不到或退出码 2 → Electron 不可用。**这是硬依赖**：按《做题前选路》退回 Draw.io 模式并在 manifest 记录 `html_engine_unavailable` 原因，不得伪造产物。
- 首次 `npx --yes electron` 会自动下载 Electron 到 npm 缓存（约 100MB，之后秒启）。

### Step 4: html_pdf_check 质检（⛔ 每张必跑，FAIL 必修）

**每出一张 PDF 就跑一次**。4 项检查：①单页（最关键，多页=FAIL，LaTeX 只显示第一页会截断）②矢量（有字体对象，非整页位图）③裁切（页面尺寸异常）④宽高比（>8:1 给 WARN）。

```powershell
python $HTMLCHECK 手绘图\fig_roadmap.pdf
# 退出码：0=通过(可能带WARN，不阻塞) 1=FAIL(必修) 2=无法检查(跳过)
```

**⛔ 若退出码 1（FAIL）**，按明细修复后**重新出 PDF 再检**，直到过：
- **多页** → 内容太多/太高：精简节点文字、减少条目、或调窄 `.fig` 的 width 让内容更紧凑；实在放不下就拆成两张图。改完回 Step 3 重出。
- **无字体/整页位图** → 检查 HTML 是否误用了 `<img>`/`canvas`/背景图代替文字，改回纯文本+CSS。
- **尺寸异常小/裁切** → 检查 `.fig` 是否 `display:inline-block` 且有内容、`body{margin:0}`。
- **宽高比过宽（WARN）** → 不阻塞，但建议：pipeline 让阶段换行、roadmap 改窄卡片。

退出码 2（如缺 PDF 解析条件）→ 跳过，不阻塞。

### Step 4.5: 元素级几何自检 + 自修复循环（⛔ 每张必跑，有问题就改到干净）

html_pdf_check 只看 PDF 结构（单页/矢量/尺寸），**看不出图里文字有没有被裁、有没有越界、两块文字有没有压在一起**。这一步用 `$CAPTURE --geom-check` **纯几何测量**（不调大模型、几十毫秒）把它们精确抓出来，然后**你亲自读 HTML 改 CSS 修好**。

**几何自检测四类问题（都在 `.fig` 内、渲染公式之后测，所以准）：**

| 类型 | 含义 | 常见成因 |
|---|---|---|
| **文字溢出被裁** | 元素实际内容宽/高 > 盒子宽/高 | 节点 `width`/`min-width` 太窄、文字太长、`overflow:hidden` 切掉 |
| **越出 .fig 边界** | 元素跑到画布外（会被论文页面裁掉） | 误用 `position:absolute` 定坐标、`margin`/`transform` 把元素推出去 |
| **文字块重叠** | 两个同级文字块几何相交、内容互相压盖 | absolute 定位撞车、负 margin、回边/侧栏占位算错（回环最易犯） |
| **对齐偏差**（声明式） | 打了 `data-mh-col`/`data-mh-row` 的同组元素中轴没对齐（极差 >4px） | 手写不同 `width`、`margin` 挪位、没用 grid 锁列/行、竖箭头没接节点中轴 |

> ⛔ **对齐偏差只对打了 `data-mh-col="k"`/`data-mh-row="k"` 标记的元素生效**（见 G.5 第 4 条）：主干/纵列的节点+竖箭头打 `data-mh-col`、同行节点打 `data-mh-row`，工具就会验证它们中轴是否成一条线。没打标记的图不触发这项。**所以画主干/多列/多行结构时务必打标记。**

**每出一张 PDF（Step 3）、过了 html_pdf_check（Step 4）后，立即跑几何自检：**

```powershell
# 无公式的图：
python $CAPTURE --geom-check 手绘图\fig_roadmap.html
# 含公式的图：必须加 --render-math（公式渲染会改变盒尺寸，不加会误报/漏报）
python $CAPTURE --geom-check 手绘图\fig_flow_q1.html --render-math
# 退出码：0=干净 1=有几何问题（必修） 2=无法检查（Electron 不可用，跳过不阻塞）
```

**⛔ 若退出码 1（有问题），进入自修复循环（最多 3 轮，每轮"检→读→改→重出→重检"）：**

1. **读报告**：工具会逐条列出「哪块文字溢出/越界/重叠、越了多少 px / 交叠多大面积」，报告里印了每块前 20 字，对得上 HTML 里的节点。
2. **用 read 工具读这张 `手绘图/<name>.html`**，按问题类型针对性改 CSS：
   - **文字溢出被裁** → 加大该节点 `min-width`/`width`，或缩短文字/移一部分到副标题 `.sub`，或调小 `font-size`（12px→11px），或去掉不该有的 `overflow:hidden`+`white-space:nowrap`。
   - **越出 .fig 边界** → ⛔ 十有八九是**误用了 `position:absolute` 定坐标**。改回 **flex/grid 自动布局**；回边/侧栏这类确需叠加的，用相对定位并给父容器留足空间。
   - **文字块重叠** → 同上，绝大多数是 absolute 或负 margin 造成。改成 flex/grid 顺排；本就该错开的（如循环回边标签）给独立的 flex 轨道或加 `gap`。
   - **对齐偏差** → 把这组元素装进 `display:grid`（列用 `grid-template-columns:<定宽或1fr>` + `justify-items:center`，行用 `grid-auto-flow:column`+`align-items:center`），节点 `width:auto;min-width:0` 交给 grid 拉齐，竖箭头放进同列容器居中——**别靠手写 width/margin 对齐**（见 G.5）。
3. **改完重出 PDF**（Step 3 命令）→ 重跑 html_pdf_check（Step 4）→ 再跑本步几何自检。
4. 循环直到退出码 0，或 3 轮用完（用完仍有问题**不阻塞**，但要记下这张需人工看一眼）。

**⛔ 与 vision 自检（Step 5）的分工**：几何自检是**精确的、必修的**；vision 是**模糊的、不阻塞的**（看配色/审美/挤不挤）。先过几何（硬门槛），再走 vision（加分项）。**FAST_MODE=1 时几何自检照跑**，只跳 vision。

### Step 5: 视觉自检（运行时原生视觉，⛔ 不阻塞）

这一步用**运行时原生视觉能力**（DSH：`read_image` / `vision_analyze`）真正"看图"：先把 PDF 转成 PNG（PyMuPDF），再逐张审查。**FAST_MODE=1 时跳过本步。**

⛔ **执行原则**：视觉能力失败或明确返回"无法查看图片"就按 skipped 记账跳过，**绝不阻塞**；这是加分项不是硬门槛，3 轮仍未解决也继续。⛔ 禁止凭文件名/尺寸/上下文猜测图面内容——审不成就是审不成，如实记 skipped。

**准备（shell）：清空三笔记账 + 把本引擎的图逐张转 PNG**：

```powershell
# ⛔ FAST_MODE 就地重判：本会话用户明确要求"快速模式/跳过视觉自检"→ 1；否则 0。
$FAST_MODE = 0

New-Item -ItemType Directory -Force -Path _tmp | Out-Null
# ⛔ 无条件清空三笔记账（防断线重跑读到上一轮残留）：
#   passed=真跑了vision且通过(执行凭证) / unresolved=审了3轮没修好(硬拦) / skipped=环境原因没审成(警告)。
Remove-Item _tmp\vision_unresolved.txt, _tmp\vision_skipped.txt, _tmp\vision_passed.txt -ErrorAction SilentlyContinue

if ($FAST_MODE -eq 1) {
    Write-Output "⚡ 快速模式：跳过 vision 视觉自检（省额度）；Step 7 的执行凭证断言仅非快速模式生效。"
}
else {
    # 只检本引擎的流程/路线图（手绘图/*.html 对应的同名 .pdf）；数据图由 Python 链路自检，不在此扫。
    $targets = Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue |
        Where-Object { Test-Path ($_.FullName -replace '\.pdf$', '.html') }
    foreach ($pdf in $targets) {
        $bn = $pdf.BaseName
        python -c "import fitz,sys; d=fitz.open(sys.argv[1]); d[0].get_pixmap(matrix=fitz.Matrix(200/72,200/72)).save(sys.argv[2])" `
            $pdf.FullName "_tmp\${bn}_v.png"
        if (Test-Path "_tmp\${bn}_v.png") { Write-Output "PNG_READY $bn" }
        else { Add-Content _tmp\vision_skipped.txt "$bn (PDF→PNG 转换失败，未审成)" }
    }
}
```

**逐张审查（read_image / vision_analyze，非 shell——由你作为 agent 执行，每张最多 3 轮）：**

对上面每个 `PNG_READY <bn>` 的图：

1. 用 `vision_analyze`（image=`_tmp/<bn>_v.png`）或 `read_image` 审查，prompt 聚焦：文字溢出/截断、节点重叠、越界、配色刺眼、布局松散、节点不对齐、箭头歪接、出现 HTML 源码/黑背景。
2. **通过** → shell 执行 `Add-Content _tmp\vision_passed.txt "<bn> PASS"`，下一张。
3. **视觉能力不可用/返回"无法查看图片"** → `Add-Content _tmp\vision_skipped.txt "<bn> (Vision 不可用/调用失败)"`，不阻塞。
4. **有视觉问题** → 逐步修复（不是只跑检测）：
   - 用 **read 工具**读该图的 `手绘图/<name>.html`。
   - 按 vision 反馈改（HTML 是相对布局，改法比 drawio 简单）：
     - "文字溢出/截断" → 加大对应节点 `min-width` 或缩短文字。
     - "配色刺眼/杂乱" → 按《设计规范 B 节》从 `H0` 重新推导色板，饱和度 ≤45%、有意义色 ≤4，别自造高饱和色。
     - "布局松散/大片留白" → 检查是否漏填内容或容器过宽。
     - ⛔ **"节点不对齐/大小参差/边缘不齐/箭头歪接/间距忽大忽小"（最常见的"丑"）** → 按 D.1 ④ 硬纪律改：并列节点改用 `grid`+`1fr`（或 flex `flex:1`+`align-items:stretch`）强制等宽等高；多行多列用 `display:grid` 让行列自动对齐；箭头 `align-items:center` 接中轴；`gap`/`padding`/`border-radius` 全篇统一。**别手写不同 width、别用 margin 挪位置。**
     - "出现 HTML 源码/黑背景" → 检查标签是否闭合、`body{margin:0}`。
   - 用 edit 工具写回 → **重新出 PDF**（Step 3）→ 重跑 html_pdf_check（Step 4）→ 重新转 PNG → 回本步重审。
   - 重复直到通过或 3 轮用完（用完仍不过也继续，不阻塞）：第 3 轮后 shell 执行 `Add-Content _tmp\vision_unresolved.txt "<bn> (3轮视觉自检未修好)"`。

### Step 5.5: TikZ 精密几何示意图（⛔ 能力保留；math-paper-huawei 锁定契约下默认关闭）

> ⛔ **math-paper-huawei 范围说明**：本节能力在 `drawing_mode=HTML矢量成图` 契约下**默认不执行**（NEED_TIKZ 恒为 0）——原理/模型/概念/几何示意图一律按锁定模式契约保留 2–4 份提示词，不自动生图，也不产生 manifest 条目。本节仅作为引擎能力文档保留，供后续单独放开该能力时参考；公式流程图走 HTML+KaTeX（Step 3 `--render-math`），本节只画 HTML 摆不准的**精密几何示意图**（按真实坐标画点/线/角度/向量场，如绳系摆几何、光路、受力分解），用 TikZ 编译成矢量 PDF。

```powershell
# 就地重判 NEED_TIKZ（锁定契约下恒为 0，除非产品明确放开该能力）
$NEED_TIKZ = 0
$XELATEX = (Get-Command xelatex -ErrorAction SilentlyContinue).Source
if ($NEED_TIKZ -ne 1) { Write-Output "ℹ 锁定契约无精密几何图需求，跳过 TikZ（Step 5.5）" }
elseif (-not $XELATEX) { Write-Output "❌ 需要但无 xelatex，无法编译——必须暴露失败，不得静默跳过" }
```

若该能力被明确启用且 `NEED_TIKZ=1` 且 `XELATEX` 可用，按以下执行：

- ⛔ **硬合同**：清单里每个 `tikz_<name>` 必须产出独立同名 `手绘图/<name>.tex` + `手绘图/<name>.pdf`（每个 .tex 可独立编译，内含**一个** `\begin{tikzpicture}`；`\documentclass{standalone}` 或 `article`+`\pagestyle{empty}`），严禁用 matplotlib/HTML 顶替、严禁跳过或改名。
- ⛔ 中文用 xelatex + `\usepackage{ctex}`（或 `fontspec` 指定中文字体），否则中文丢失。图内不写标题；图内文字语言 = `$FIG_LANG`。
- ⛔ **TikZ 物理尺寸 vs 字号匹配规则**：任何标注节点的可用空间 **≥ 字号 × 2**；`min(width,height) < 3cm` → 必须 `scale=2.0+`；标注层间距 < 0.5cm 会撞 → 拉大或减层；别用 `\resizebox` 放大小图。
- **逐个编译 + 修复循环（每张最多 3 轮）**：`& $XELATEX -interaction=nonstopmode -output-directory=手绘图 手绘图\<name>.tex`；编译失败读 .tex 修数学模式配对/缺 `\usetikzlibrary`/中文 ctex。
- ⛔ **失败兜底**：3 轮编不出，**大幅精简**（去掉次要标注、拆图、公式改行内文字）再试；仍不行保留其余已成功产物并明确记录失败，**不得伪造产物**。

### Step 6: 论文回填（⛔ 每张 PDF 都要入 `论文/main.tex`）

把每张 `手绘图/<name>.pdf` 用 figure 环境正式插入 `论文/main.tex` 对应位置（技术路线图在问题重述/模型建立前的总览位置，问题分析/求解流程图进对应"问题 X"章节；GMCMthesis 模板结构不得改动）：

```latex
% === 技术路线图 ===
\begin{figure}[H]
\centering
\includegraphics[width=\textwidth,height=0.7\textheight,keepaspectratio]{手绘图/fig_roadmap.pdf}
\caption{整体技术路线图}\label{fig:roadmap}
\end{figure}
```

**尺寸初值表**（width 决定实际大小，height 只是防溢出上限；`keepaspectratio` 下取更小约束）：

| 图类型 | width | height（防溢出上限） |
|---|---|---|
| 技术路线图 | `\textwidth` | `0.7\textheight` |
| 问题分析流程图 | `0.82\textwidth` | `0.55\textheight` |
| 求解流程图 | `0.82\textwidth` | `0.55\textheight` |

⛔ 所有图必须有 `keepaspectratio`。⛔ caption 必须与 `competition_language` 一致，由你按图意写。

**⛔⛔ 插入完全部 figure 块后，必须跑 `fig_include_size.py` 按每张图的真实长宽比自动规整宽度**（上表只是初值；此脚本读 PDF 实际尺寸精确纠正——横图放宽、竖长条收窄，从根上治「竖图按页宽拉伸后撑满整页」）：

```powershell
python $INCSIZE --figdir 手绘图 --latex 论文\main.tex 2>&1 | Select-Object -Last 20
# 按 高/宽 分档: ≤0.8→0.85\textwidth / ≤1.2→0.7 / ≤1.6→0.5 / >1.6→0.42; height 一律≤0.8\textheight
# 全软失败: 某图 PDF 读不到就保持原样, 不破坏文件; 只改 width/height, keepaspectratio/caption/label/路径都不动
```

> 这是确定性兜底：即便初值填得不合适、或某张图恰好竖长，脚本都会按实测比例修正到与正文协调的宽度。**跑完它，尺寸就是最终值。**

**⛔⛔ caption 长度铁律**：caption 只写**图的类别/主题**，≤ 20 个汉字（英文 ≤ 12 词），例如「求解流程图」「问题一求解流程」「整体技术路线图」。**禁止把整段方法描述、模型名称罗列、步骤枚举塞进 caption**。详细说明写进正文。

**⛔⛔ 尺寸铁律（必读）**：竖向长条流程图按 width 缩放后自然高度常超过一页，`keepaspectratio` 下 height 上限会反过来成为实际尺寸 → 图被撑满整页。**因此 height 上限已一律压到 ≤ 0.7\textheight**，禁止再回调。更根本的解法在**图本身的布局**：
- ⛔ **流程图优先横向（从左到右）或网格布局，不要画成纯竖向长条**。3~5 步的流程用横向流水线；步骤多时用「分组横排 + 少量换行」而非一路竖下来。
- ⛔ 竖向布局仅在逻辑上确有强上下依赖（如迭代循环）时才用，且尽量把并列分支横向摊开，压低总高度。
- 目标：出的 PDF 宽高比接近 4:3 ~ 16:9，**不要接近或超过 1:1.5 的瘦高比**。

**⛔⛔ 技术路线图 / 求解流程图 骨架池（治「单调、一根线」+ 保证「每人每题不一样」）**：**禁止**画成「A→B→C→D」一条横线。改为从下面 **4 个精致骨架里按 Step1 的 `SKELETON` 值选一个**（`SKELETON=(SEED/29)%4`）——不同项目种子不同 → 抽到不同骨架 → 千人千面；每个骨架都验证过「精致 + 连线可靠 + 不撑页」：

| `SKELETON` | 骨架（=manifest `template_id`） | 结构 | 连线 |
|---|---|---|---|
| 0 | **横向泳道** `skeleton_swimlane` | 2~4 个阶段带纵向堆叠，带内横排节点，左侧竖排阶段标签 | 阶段间竖箭头 |
| 1 | **竖向主干+侧挂** `skeleton_spine` | 主干节点竖直串(定宽列)，每个主干右侧横线挂出该阶段的方法/产出 | 竖箭头串主干 + 横线挂侧节点 |
| 2 | **左右双栏对照** `skeleton_twocolumn` | 左列「子问题/目标」右列「方法/模型」，逐行对应 | 左右配对横线(带箭头) |
| 3 | **分层堆叠** `skeleton_layered` | 每层一个带框阶段带(层内横排)，层间竖箭头，层左侧标题 | 纯竖箭头串层 |

- ⛔ **配色默认纯黑白 C**（见 Step1；最不 AI 感）；用户手选才切现代/朴素。**布局骨架按 LAYOUT 随机**。合起来：黑白基调(不 AI、精致) × 4 骨架轮换(千人千面)。
- ⛔ **连线可靠铁律**：固定宽度的并排结构(双栏/主干列)**必须用 `display:grid;grid-template-columns:<定宽> ...`**，⛔ **禁用 `flex:0 0 <固定px>` + 外层 `fit-content` 混搭**——那样 fit-content 算不对总宽、节点会越出右边界(geom-check 会 FAIL)。竖箭头放与主干**同宽的容器**里居中；横挂线从节点边缘起、接对侧节点。
- ⛔ **对齐标记(4 骨架都要打)**：主干列/纵向节点+其间竖箭头打 `data-mh-col="1"`(第二列 `"2"`)，同一行对照节点打 `data-mh-row="1"`——`--geom-check` 会验证同组中轴是否成一条线。
- ⛔ 每张出图后**必过 `--geom-check`**。骨架只是脚手架，**节点必须填本题真实实体**(守 A.1)。

**回填后自检**：
```powershell
Write-Output "=== main.tex 回填验证 ==="
$_tex = Get-Content 论文\main.tex -Raw
foreach ($pdf in (Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue)) {
    if ($_tex -like "*" + $pdf.Name + "*") { Write-Output "✅ $($pdf.Name) 已入文" } else { Write-Output "❌ $($pdf.Name) MISSING — 需插入" }
}
$labels = [regex]::Matches($_tex, '\\label\{fig:[^}]*\}') | ForEach-Object Value | Group-Object | Where-Object Count -gt 1
if (-not $labels) { Write-Output "✅ 无重复 figure label" } else { Write-Output "❌ 重复 label: $(($labels | ForEach-Object Name) -join ', ')" }
```
有 ❌ 立即修复（补插 figure 块 / 改重复 label）。技术路线图未入文会直接触发 `check_roadmap_in_paper` 门禁失败。

### Step 7: 最终质量门（⛔ MUST PASS，不允许带 ❌ 结束）

```powershell
Write-Output "=========================================="
Write-Output "  HTML FIGURE QUALITY GATE"
Write-Output "=========================================="
$GATE_FAIL = 0
$HTML_COUNT = (Get-ChildItem 手绘图\*.html -ErrorAction SilentlyContinue).Count
$PDF_OK = 0
foreach ($hf in (Get-ChildItem 手绘图\*.html -ErrorAction SilentlyContinue)) {
    $bn = $hf.BaseName
    if (Test-Path "手绘图\$bn.pdf") {
        # 每张 PDF 过一遍 html_pdf_check（FAIL 计入门禁）
        $hcOut = python $HTMLCHECK "手绘图\$bn.pdf" 2>&1
        if ($LASTEXITCODE -eq 1) {
            Write-Output "❌ ${bn}.pdf html_pdf_check FAIL"; $GATE_FAIL++
        } else { $PDF_OK++ }
        # 元素级几何自检（--render-math 无公式时无害）。退出码1=有问题计入门禁
        $gcOut = python $CAPTURE --geom-check "手绘图\$bn.html" --render-math 2>&1
        if ($LASTEXITCODE -eq 1) { Write-Output "❌ ${bn} 几何自检有问题"; $GATE_FAIL++ }
        # 交付 PNG 三件套齐全
        if (-not (Test-Path "手绘图\$bn.png")) { Write-Output "❌ ${bn}.png 缺失（2× 交付 PNG）"; $GATE_FAIL++ }
    }
    else { Write-Output "❌ ${bn}.html 无对应 PDF"; $GATE_FAIL++ }
}
if ($HTML_COUNT -gt 0) { Write-Output "✅ HTML=$HTML_COUNT, PDF 过检=$PDF_OK" } else { Write-Output "❌ 无 HTML 图（清单要求时为 FAIL）"; $GATE_FAIL++ }

# ⛔ 结算 Step 5 视觉自检两笔账：
if ((Test-Path _tmp\vision_unresolved.txt) -and ((Get-Item _tmp\vision_unresolved.txt).Length -gt 0)) {
    $unres = Get-Content _tmp\vision_unresolved.txt | Where-Object { $_ }
    Write-Output "❌ 视觉审查未通过 $($unres.Count) 张："; $unres | ForEach-Object { Write-Output "     - $_" }
    $GATE_FAIL += $unres.Count
}
if ((Test-Path _tmp\vision_skipped.txt) -and ((Get-Item _tmp\vision_skipped.txt).Length -gt 0)) {
    $skip = Get-Content _tmp\vision_skipped.txt | Where-Object { $_ }
    Write-Output "🟥 警告：$($skip.Count) 张图【未做视觉审查】（遮挡类问题可能漏网）"
}

# ⛔⛔ 执行凭证断言（防"没跑却当跑了"；FAST_MODE=1 不生效）：
$FAST_MODE = 0   # 就地重判
if ($FAST_MODE -ne 1) {
    $ledger = @()
    foreach ($lf in @('_tmp\vision_passed.txt','_tmp\vision_unresolved.txt','_tmp\vision_skipped.txt')) {
        if (Test-Path $lf) { $ledger += (Get-Content $lf | Where-Object { $_ }) }
    }
    $ledgerNames = $ledger | ForEach-Object { ($_ -split '\s+')[0] }
    $noVerdict = 0
    foreach ($pdf in (Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue | Where-Object { Test-Path ($_.FullName -replace '\.pdf$', '.html') })) {
        $vb = $pdf.BaseName
        if ($ledgerNames -notcontains $vb) {
            Write-Output "❌ 执行凭证缺失：$vb 三笔视觉账都无记录 —— 视觉自检被静默跳过，必须真跑 Step 5 再复核"
            $noVerdict++
        }
    }
    if ($noVerdict -gt 0) { $GATE_FAIL += $noVerdict }
    else { Write-Output "✅ 视觉自检执行凭证齐全" }
}

# manifest 对账：每个 <name> 必须有完整九字段条目（generator=html）
$mani = Get-Content figures\manifest.json -Raw | ConvertFrom-Json
foreach ($hf in (Get-ChildItem 手绘图\*.html -ErrorAction SilentlyContinue)) {
    $bn = $hf.BaseName
    $entry = @($mani.items | Where-Object { $_.source -like "*$bn.html" }) | Select-Object -First 1
    if (-not $entry) { Write-Output "❌ manifest 缺 $bn 条目"; $GATE_FAIL++ }
    elseif ($entry.generator -ne 'html') { Write-Output "❌ manifest $bn generator 应为 html"; $GATE_FAIL++ }
}

# 论文回填核对
if (Test-Path 论文\main.tex) {
    $_tex = Get-Content 论文\main.tex -Raw
    foreach ($pdf in (Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue)) {
        if (-not ($_tex -like "*" + $pdf.Name + "*")) { Write-Output "❌ $($pdf.Name) 未插入论文"; $GATE_FAIL++ }
    }
} else { Write-Output "⚠ 论文/main.tex 尚未创建（step4 前属正常，回填随 step4 完成）" }

# 无损坏小 PDF
foreach ($pdf in (Get-ChildItem 手绘图\*.pdf -ErrorAction SilentlyContinue)) {
    if ($pdf.Length -lt 3000) { Write-Output "❌ $($pdf.Name) 仅 $($pdf.Length) 字节，疑损坏"; $GATE_FAIL++ }
}

Write-Output ""
if ($GATE_FAIL -eq 0) { Write-Output "✅ ALL PASSED" } else { Write-Output "❌ $GATE_FAIL FAILURES — 逐个修复后重跑本门禁" }
```

**⛔ 若 GATE_FAIL > 0**：逐个修复每个 ❌（重生成 HTML→重出 PDF→重检，或补插论文/补 manifest），重跑门禁，直到 GATE_FAIL=0。若某张 HTML 图 html_pdf_check 反复多页，最后手段是拆图或大幅精简内容。

**⛔ 全通过后输出最终 CHECKLIST 确认：**
```
HTML PLAN CHECKLIST (FINAL):
[✅] 1. fig_roadmap  — 手绘图/fig_roadmap.{html,pdf,png} — html_pdf_check PASS + geom-check PASS
[✅] 2. fig_flow_q1  — 手绘图/fig_flow_q1.{html,pdf,png} — PASS
[✅] manifest — 每张图九字段条目齐全（generator=html）
[✅] 论文/main.tex — 每张 PDF 已 \includegraphics 入文
ALL COMPLETE — HTML 矢量成图完成
```

## figures/manifest.json 对账（math-paper-huawei 门禁代行）

上游 FIGURE_MANIFEST 区块对账在本技能下由 `figures/manifest.json` + `check_drawing_contract.py` 门禁代行，要点：

- manifest 顶层含 `drawing_mode: "html"`、`drawing_mode_locked: true` 与 `items` 列表，与 `项目状态.json` 一致（不一致直接门禁失败）。
- 每个非数据绘图条目九字段见《Output Contract》；`chart_family` 可标 `flowchart`/`roadmap` 便于流程类图识别。
- 概念类提示词 2–4 份仍写在 `手绘图/*.md`（与 Draw.io 模式同一目录同一口径），且**不得**出现 AI 成图或 drawio 条目混入。
- 数据图（matplotlib）条目沿用既有字段，不进本引擎。

## Key Rules（速查）

- HTML 用 flex/grid 自动布局，**不写绝对坐标** → 免疫重叠/错位/连线穿越（相对 drawio 的核心优势）。
- 单文件自包含：CSS 变量内联在 `<style>`，**不引 CDN/网络资源**（离线环境）；字体按 `STYLE_FAMILY` 用系统栈（见 0 节硬约束 4）+ `font-variant-numeric:tabular-nums`。
- ⛔ 画布透明：`html`/`body`/`.fig` 背景一律 `transparent`，**整图不铺底色块**（融入论文页面），只有节点自身可浅填充。
- 出图：`python $CAPTURE --file 手绘图\<name>.html --out 手绘图\<name>.pdf --format pdf` → 单页矢量无白边。
- ⛔ 用 `python` 不用 `python3`（Windows 下 python3 触发 Store 存根）。
- ⛔ **图内不写标题**，标题交给 LaTeX `\caption{}`；图内文字语言与 `competition_language` 一致。
- ⛔ 配色由 Step 1 风格种子 `H0` 按《设计规范 B 节》HSL 推导，全篇共用同一 `H0`/`TONE`；别自造高饱和色、别逐图换色、别用随机数。
- ⛔ 逐张画 → 转 PDF → html_pdf_check（FAIL 必修）→ **几何自检 `--geom-check`（有问题必修，最多3轮）**→ vision 自检（不阻塞）→ 交付 PNG → 过了再画下一张。
- ⛔ 每张 PDF 都要在 `论文/main.tex` 有 `\includegraphics` 块并跑 `fig_include_size.py` 规整宽度。
- html_pdf_check 退出码：0=通过 / 1=FAIL 必修 / 2=无法检查跳过。多页 PDF 是最常见 FAIL（LaTeX 只显示第一页）。
- ✅ **公式直接写 HTML + `--render-math`**：节点里用 `\(...\)`/`\[...\]` 写公式，KaTeX 渲染成矢量公式，不必为公式退回 TikZ。
- ⛔ 运行时只读取本技能内置 `assets/html-figure/`，禁止读取外部 `html-paper-figure` 目录；Electron 不可用时按选路规则退回 Draw.io 模式并记录原因。

---

## AI 自主生成 HTML 流程图设计规范

> Step 2 逐张设计时的唯一准绳。目标：**每张图的结构忠实于它自己的逻辑，配色/造型由风格种子确定性推导**，从而同篇统一、异篇各异、单张之间因逻辑不同而不雷同，同时始终高级、克制、符合科研/竞赛审美。

### 0 硬约束（⛔ 违反即出图失败，无例外）

1. **一路 `fit-content` 收缩到内容**：`html, body` 与最外层根容器都必须
   ```css
   html, body { margin:0; padding:0; width:fit-content; height:fit-content; background:transparent; }
   .fig { width:fit-content; height:fit-content; background:transparent; }
   ```
   根容器**不允许**出现固定像素宽（如 `width:640px`）或 `100%/100vw`——否则 Electron 会量到视口宽 1280px，PDF 右侧留大白边。留白靠内部 `padding`/`gap`，不靠外层撑宽。
2. **⛔ 整图不设背景色块**：`html`/`body`/`.fig` 背景一律 `transparent`，**不给整张画布铺任何底色**（哪怕近白 `#fff`/`#fafafa` 也不行）。图要能无缝融入论文页面。只有**节点自身**可有浅填充（见 D 节 `--node-bg`），画布本身透明。
3. **flex/grid 自动布局，禁 `position:absolute` 定坐标**：节点、连线、分区一律用 flex/grid 排布。自动布局是"永不重叠/错位/连线穿越"的根本。
4. **单文件自包含，禁外链**：CSS 内联在 `<style>`；不引 CDN、不引网络字体、不引外部图片。⛔ **字体走系统栈（离线安全，全是 Win/Mac 自带字体），且按 `STYLE_FAMILY` 选字体族**（见文末《G 风格族》）：
   ```css
   /* STYLE_FAMILY=1（B 现代精致风）：无衬线现代体 —— 西文优先，中文 fallback 雅黑/思源 */
   .fig,.fig *{
     font-family:"Segoe UI","Helvetica Neue",Helvetica,Arial,"Microsoft YaHei","Noto Sans SC",sans-serif;
     font-variant-numeric:tabular-nums;   /* 等宽数字：参数/指标竖直对齐 */
     -webkit-font-smoothing:antialiased;
   }
   /* STYLE_FAMILY=0（A 朴素竞赛风）或 2（C 纯黑白线稿）：衬线印刷体 —— 贴近论文正文/黑白框图观感 */
   .fig,.fig *{
     font-family:"Times New Roman","SimSun","Songti SC","Microsoft YaHei",serif;
     -webkit-font-smoothing:antialiased;
   }
   ```
   ⛔ **只保留 `STYLE_FAMILY` 对应的那一套 `.fig,.fig *` 字体规则，删掉其它**：`FAMILY=1` 用无衬线；`FAMILY=0` 和 `FAMILY=2` 都用衬线。西文字体族排在中文前 → 英文/数字用西文字形（更精致），中文自动 fallback。**别把中文字体排第一**。
5. **图内不写标题**：标题交给 LaTeX `\caption{}`，图里只有流程/结构本身。
6. **单页 + 宽高比 ≤ 8:1**：内容多时优先增高不增宽（或分区换行），别撑成超宽单行。
7. **公式写 `\(...\)`/`\[...\]`**：节点里的数学公式用 KaTeX 定界符包裹，出图加 `--render-math` 渲染。
8. **禁 emoji、禁装饰性图标字体**。
9. **⛔ 节点文字禁出现 LaTeX 排版命令**：这是 HTML 不是 LaTeX。节点/副标题/标签里**严禁**写 `\scriptsize`、`\small`、`\footnotesize`、`\bfseries`、`\textbf`、`\centering`、`\node`、`\hline` 等任何 LaTeX 排版/绘图命令——它们不会被渲染，会原样显示成乱字。字号一律用 CSS `font-size`、字重用 `font-weight`、对齐用 `text-align`。**唯一例外**：`\(...\)`/`\[...\]` 里的数学内容（第 7 条），那是 KaTeX 公式，不是排版命令。

### A 结构忠实于逻辑（⛔ 废除"强制三件套"）

**结构服务逻辑，不为花样而花样。** 线性的问题就画线性，迭代的问题才画循环，并行的问题才画分叉。

**设计前先用一句话说清这张图的逻辑流向**，再从下表按逻辑选范式。⛔ **多数逻辑列了【多个等价范式】（编号从 `⓪` 起：`⓪①②`）**——按 Step 1 的 `LAYOUT` 种子确定性选：选编号 `= (LAYOUT % 该逻辑的候选数)` 的那个。这让同类题的不同用户宏观骨架也不同。

| 逻辑类型 | 等价范式（选编号 `= LAYOUT % 候选数`，⓪ 表示第 0 个） |
|---|---|
| 线性顺序（A→B→C→D） | ⓪纵向主干 / ①横向流水线 |
| 阶段推进 / 时间演进 | ⓪时间轴（横向刻度） / ①分层堆叠（自上而下阶段） |
| 有条件分支 | ⓪上下分叉树 / ①左右对照分叉（均圆角矩形判定节点→是/否两路，⛔ 不用旋转菱形，见 A.2 骨架 3） |
| 迭代 / 收敛 | ⓪纵向循环回流 / ①横向循环回流（均带回边箭头 + 收敛判断出口） |
| 多任务并行后汇总 | ⓪竖向并行列→底部汇合 / ①横向并行行→右侧汇合 |
| 输入/处理/输出三段 | ⓪横向泳道 / ①左右对照 |
| 模块化系统 | ⓪分层堆叠 / ①矩阵网格 |
| 以核心方法为中心辐射 | ⓪放射中心（3×3，见 A.2 骨架 2）——语义唯一，不参与 LAYOUT 选择 |
| 方法/维度对比 | ⓪矩阵网格 / ①左右对照 |

⛔ **放射中心不进"模块化系统"候选**：放射中心要求有一个**真正统领全局的核心引擎**。模块化系统若无这种中心语义，硬选放射中心会编造假中心、违反 A.1 反空壳。

⛔⛔ **LAYOUT 铁律**：`LAYOUT` **只在【逻辑等价】的编号范式间选**——迭代题的两个候选都是循环，并行题的两个候选都是分叉。**绝不允许**为了套 `LAYOUT` 把迭代题选成线性。**先保证逻辑忠实（A 节铁律），再在等价范式内用 LAYOUT 拉开骨架差异**——顺序不能反。

**⛔ 换骨架不等于降对齐**：选了横向/放射/分层骨架后，仍须满足 D.1 ④ 对齐硬纪律。

**⛔ 规模兜底（种子不凌驾于排版合理）**：若 `LAYOUT` 选出的朝向与节点数量打架——**横向范式但节点 ≥6 会撑出超宽图**，或纵向范式但节点 ≥8 会拉成细长条——则**换用同逻辑的另一个等价范式**。判定优先级：**逻辑忠实 > 排版合理 > LAYOUT 骨架多样**。

**自检问题**：如果把某个判断/循环去掉后，这张图描述的逻辑依然成立——那这个判断/循环就是硬凑的，删掉。宁可结构简单而**准确**，不要为了"看起来复杂"而失真。

**不同子问题必须看得出差异**：q1/q2/q3 若算法逻辑不同，它们的布局范式就应当不同。

**⛔ A.1 反"通用空壳"——图必须有这篇论文特有的内核（违反即返工）**

"结构服从逻辑"不是"允许偷懒画泛泛流程"。⛔ **严禁**画出换任何论文都成立的通用空壳，典型反例：节点全是万能词 `数据采集 → 数据预处理 → 建立模型 → 模型求解 → 结果分析 → 结论建议`。信息量≈0，**一律返工**。

**每张图必须做到两点：**

1. **节点承载实体，不写空词**：节点里填**这个子问题特有的**方法名/模型名/算法/判据/关键变量/关键约束。
   - ❌ `建立模型` → ✅ `多目标遗传算法 NSGA-II`、`时变需求下的库存 (s,S) 策略`
   - ❌ `数据预处理` → ✅ `3σ 剔除异常 + 样条插补缺失`、`滑动窗口去趋势`
   - ❌ `模型求解` → ✅ `Gurobi 求解 MILP（分支定界）`、`四阶 Runge-Kutta 数值积分`

2. **挖出方法真实的非平凡结构**：参数标定回调、假设检验分支、收敛判断回环、多方法并行对比后择优、灵敏度/稳健性反馈。**把真实存在的结构挖出来画上**（这不是硬凑，是忠实）。⛔ 但仍守 A 节铁律：只画**真实存在**的结构，不编造原逻辑里没有的分支/循环。
   - 判据：问自己"这道题的方法，除了顺序执行，还有没有回头校验、条件切换、并行比选？"——有就画出来，别把它拉直成一根线。

**⛔ A.1′ 节点写"方法与步骤"，不写"具体结果数值"（技术路线图/流程图不是结果展示区）**

技术路线图/求解流程图画的是**做什么、用什么方法、得到什么量**的框架；**具体求解结果数值属于结果图表和正文，绝不塞进流程图节点**（既喧宾夺主，又常与正文精度对不上，还会连带触发数字溯源审计）。
- ✅ 正确：`求解得到临界时刻 t*`、`输出最优螺距 p_min`、`时间二分求根至 1e-6 s`（算法收敛精度/迭代设定属**方法参数**，可保留）
- ❌ 错误：`输出：t*=412.473838 s`、`交叉验证误差 7.01e-8`（这些是**求解产出的结果值**，只能出现在结果图表/正文）
- 判据：某个数字如果来自 `results/final_results.json`（是"算出来的结果"），就不该进流程图节点；如果是算法本身的固定设定（精度阈值、迭代上限），可以留。

**⛔ 内核自检（每张图出图前必过）**：把所有节点文字抄下来，遮住题目，问"光看这些节点，能认出这是哪类课题、哪个方法吗？"——认不出 = 太泛，回去填实体、挖结构，重画。

### A.2 复杂范式 CSS 骨架库（⛔ 复杂结构照此搭，别退化成一根线）

菜单里"分层架构""放射中心""贯穿侧栏"这类**高级范式**光有名字画不出档次。下面给**可直接照抄的 flex/grid 骨架**。⛔⛔ **注意：下方骨架里的旧变量名是历史示例，务必按新 B 节改成黑白基调**——`--node-bg/-2/-3`→灰阶 `--n-bg/--n-bg2`（`#f4f4f4/#ececec`），`--line`→灰边 `--n-line`，`--primary-dark`→近黑 `--text`；**尤其 `background:var(--primary);color:#fff` 这种实心彩底+白字一律禁用**，核心/焦点节点改用 `--accent-bg` 浅底 + `--text` 深字 + `--accent` 粗边。彩色只落焦点/语义连线/(TONE1)类型边框。

**骨架 1 · 分层系统架构 + 贯穿侧栏**（多层堆叠，每层多模块，右侧横切关注点贯穿全层）：

```css
.fig{display:flex;flex-direction:row;align-items:stretch;gap:14px}  /* 主栈 + 侧栏并排 */
.stack{display:flex;flex-direction:column;gap:0}                     /* 各层竖向堆叠 */
.layer{background:#ececec;border:1.1px solid #c9c9c9;border-radius:8px;
  padding:11px 14px;display:flex;align-items:center;gap:14px}        /* 一层=灰阶分区块面 */
.layer .lname{writing-mode:vertical-rl;font-size:11px;font-weight:700;
  color:var(--text);letter-spacing:2px;white-space:nowrap}          /* 竖排层名(近黑) */
.mods{display:flex;gap:11px}                                         /* 层内模块横排 */
.flow{text-align:center;color:#8a8a8a;font-size:15px;margin:3px 0}   /* 层间数据流箭头(灰) */
.side{background:var(--accent-bg);border:1.1px solid var(--accent);  /* 侧栏=唯一可带H0色处 */
  border-radius:8px;padding:12px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:11px;align-self:stretch}
```
- 层间流写"↑ 决策下发　状态上报 ↓"这类**双向语义**，别只画单箭头。
- 侧栏放"横切关注点"（安全/监控/反馈闭环），用 `--accent` 虚线框区别于主栈。

**骨架 2 · 放射中心（3×3 网格，核心引擎四周辐射）**：

```css
.grid{display:grid;grid-template-columns:repeat(3,150px);grid-template-rows:repeat(3,auto);
  gap:20px 26px;align-items:center;justify-items:center}
.core{grid-column:2;grid-row:2;background:var(--accent-bg);color:var(--text);
  border:2px solid var(--accent);border-radius:10px;padding:16px 14px;font-weight:700}
  /* 正中核心=全图唯一焦点：H0 浅底+深字+粗彩边，不用实心彩底+白字 */
.node{background:#f4f4f4;border:1px solid #c9c9c9;color:var(--text)}  /* 四周节点全灰阶 */
```

**骨架 3 · 多分区块面（泳道/阶段分区，区内放节点）**：

```css
.zone{background:#ececec;border:1.1px solid #c9c9c9;border-radius:8px;
  padding:13px 16px;display:flex;flex-direction:column;align-items:center;gap:9px}/* 灰阶分区 */
.zone .zt{font-size:11px;font-weight:700;color:var(--text);letter-spacing:1px}/* 区标题(近黑) */
.row{display:flex;gap:14px}                          /* 区内节点横排 */
.branch{display:flex;gap:52px;align-items:flex-start} /* 条件分支：多路并列 */
```
- 分支范式：**判定节点下接 `.branch`**，每路一个 `.path`（含 `.lbl` 标"是/否""成立/违背"），再 `.merge` 汇合。
- ⛔⛔ **判定节点一律用圆角矩形，禁用旋转菱形（`transform:rotate(45deg)` / clip-path 菱形）**：旋转后布局盒仍是正方形，尖角会压住相邻节点（真实翻车）。判定语义靠**下方两条带"是/否"标签的分支箭头**表达。判定节点写法：`border-radius:var(--r)` 的普通节点 + 稍粗边或 `--accent` 边框以示"这是判定"，文字精简成一行。

**⛔ 骨架只是脚手架**：结构照搭，**节点文字必须换成本题真实实体**（守 A.1）；配色变量必须按 B 节从 `H0` 推导。

### B 配色配方（⛔ 从种子 H0 用 HSL 推导，示例数值不得照抄）

Step 1 已算出主色相 `H0`（0–359 的整数）。**按下表用 HSL 推导整套色板**，每张图开头写成 `:root` CSS 变量。同一篇论文所有图共用同一 `H0`，所以色板自动统一。

⛔⛔ **核心原则**：**节点主体一律走黑白灰**，`H0` 推导的彩色**只用于三处**——①全图唯一焦点 ②语义连线/判断分支（是/否、回流）③描边档(TONE 1)的类型边框。**绝不给每个节点填不同颜色**。一张图里彩色占比目测 ≤15%，其余全是灰阶。

| 角色 | 变量 | 推导规则（H=色相 S=饱和 L=亮度） | 用途 |
|---|---|---|---|
| **灰阶·节点底** | `--n-bg` | `#f4f4f4`（中性浅灰，无色相） | 普通节点填充（TONE 2 用） |
| **灰阶·分区底** | `--n-bg2` | `#ececec` | 分区/泳道填充（TONE 2） |
| **灰阶·边框** | `--n-line` | `#c9c9c9`~`#2b2b2b`（按档选，无色相） | 节点边框/连线 |
| **灰阶·正文字** | `--text` | `#1a1a1a`（近黑，无色相） | 节点内文字 |
| **灰阶·弱文字** | `--muted` | `#6b6b6b` | 副标题/注释 |
| 强调色 | `--accent` | `hsl(H0, 42%, 45%)` | ⛔ **只用于唯一焦点的边+字、语义分支标签、回流箭头** |
| 焦点浅底 | `--accent-bg` | `hsl(H0, 40%, 95%)` | 唯一焦点节点的柔和浅底（仅此一个节点可有色底） |
| 类型边框 | `--type-a/-b` | `hsl(H0,38%,48%)` / `hsl((H0+35)%360,32%,50%)` | **仅 TONE 1(描边档)** 用 |
| 画布底 | —（无变量） | `transparent` | ⛔ 整图不铺底色 |

**⛔ 配色约束（违反即返工）：**
- **节点主体黑白灰，彩色只做强调**：普通节点用 `--n-bg`/白底 + 灰边 + 深字。⛔ **禁止用 H0 彩色填充多个普通节点**。
- `--accent` 饱和度 **≤ 45%**（低饱和才高级），且**全图彩色占比 ≤15%**。
- **画布背景必须 `transparent`**；文字用近黑 `--text`。
- 主文字对比度 **≥ 7:1**。
- **强调色只 1 种色相（H0 派生），语义连线复用它**；不引入第二种彩色色相。
- **B.1 H0 决定"这篇的强调色"**：可选学科吸附——能源/环境≈170（青绿）、经济/管理≈35（暖橙）、计算机/信息≈225（靛蓝）、通用≈210（灰蓝）。吸附后全篇一致。⛔ H0 只染那 ≤15% 的强调部分，不染节点主体。

### C 同篇统一 + 异篇不同（确定性，非随机）

- **种子 = 项目根目录名的哈希**（Step 1 已算）。同一篇论文所有图读到同一 `SEED`，因此配色/造型/布局倾向全篇一致。
- **不同论文/不同项目目录名不同 → SEED 不同 → H0/TONE 不同 → 整体风格明显不同。**
- **断线重跑同目录 → SEED 不变 → 风格可复现。**
- **单张图之间的差异只允许来自"逻辑不同"**（A 节的范式选择），不允许来自配色/造型漂移。
- ⛔ **绝对禁止**用随机数、时间戳、`$RANDOM`、当前时间等非确定性来源决定任何视觉参数。

### D 造型档次（由 TONE 选一种，全篇统一）——三档都是"黑白基调 + H0 强调"

Step 1 的 `TONE`（0/1/2）决定全篇统一的造型档，**三档都以黑白灰为主体、彩色只做强调**：

| TONE | 档名 | 节点主体 | H0 彩色只用在 | 层次靠 |
|---|---|---|---|---|
| **0** | **纯黑白线稿** | 全白底、`--n-line` 黑灰细边、零填充 | **语义连线/分支**（是/否/回流标签）+ 焦点更粗黑边 | 边框粗细 + 字重 + 留白，**完全不靠填色** |
| **1** | **彩边白卡** | 白底、**彩色边框**按节点类型分（`--type-a`/`--type-b`）、圆角卡片 | **节点边框**（类型区分）+ 焦点粗边 | 边框颜色/粗细 + 极淡阴影 |
| **2** | **灰阶分区 + 单焦点** | `--n-bg`/`--n-bg2` 灰阶填充分层 | **仅唯一焦点**（`--accent-bg`浅底+`--accent`边字），其余全灰 | 灰阶深浅 + 唯一彩色焦点 |

⛔ **三档共同铁律**：节点主体永远黑白灰；`H0` 彩色占全图 ≤15%。**任何档都不许把多个普通节点填成不同彩色**。

**通用造型规则（三档都遵守）：**
- **圆角统一**：全图同一圆角值，⛔ **具体值以《G 风格族》为准**——A 族直角~2px、B 族 5px（`RADIUS` 旋钮在各族封顶内微调），别混用。
- **边框 1–2.2px**：TONE 0 用近黑 `#2b2b2b`(1.2px)、焦点 2.2px 纯黑；TONE 1/2 用灰边或类型彩边(1–1.4px)、焦点 2px。
- **阴影克制**：最多 `0 1px 3px rgba(0,0,0,0.06)`；TONE 0 纯线稿**完全不用阴影**。
- **留白呼吸**：节点内 `padding` ≥ 10–16px，节点间 `gap` ≥ 14–20px。
- **字号层级**：主节点 14–16px、说明文字 12–13px、注释 11px；同层级字号一致。
- **字重梯度（高端细节）**：焦点/核心 `700`、主节点 `600`、普通节点 `500`、副标题/注释 `400`——**用字重拉层次而非字号跳变**。
- **字间距**：全大写英文标签/分区名加 `letter-spacing:.5–1px`；正文中文不加字间距；数字统一 `font-variant-numeric:tabular-nums`。
- **箭头造型**：细箭头（CSS 三角或 `border` 画），颜色 `--line`；线宽与节点边框协调。
- **反面清单（出现即返工）**：高饱和原色、粗黑边、大面积渐变、多种圆角混用、彩虹配色、emoji、装饰性图标。

### D.1 高级科研审美细节（⛔ 这些细节决定"看起来高级"还是"像 PPT 草稿"）

**① 层次靠"轻重"而非"多色"**：区分主次优先用**字重 + 留白 + 深浅灰**，不是加新颜色。主节点 `font-weight:700` + 略深灰底/白底；次节点 `font-weight:400` + 无填充。⛔ 别靠"每类一个颜色"区分。

**② 连线是"信息"不是"装饰"**：箭头细、短、语义化。多源汇入用倾斜箭头 `↘ ↓ ↙` 收拢到一点；回流/反馈用**虚线 + `--accent`** 与主流区分；双向流写清"上行/下行"语义。这里是 H0 彩色**允许出现**的地方之一。⛔ 禁纯直角折线堆叠、禁多条线交叉穿越（flex/grid 天然避免，别手动 absolute 破坏它）。

**③ 副标题制造信息密度**：每个节点主标题下加一行 `.sub`（`font-size:10-11px；color:--muted`）写方法细节/参数/数据源。这一行是"内行感"的来源，也直接支撑 A.1 内核。

**④ ⛔⛔ 对齐与整齐（硬性纪律，一票否决）**：
- **同一行/同一列的并列节点必须等宽等高**：用 `grid` + `grid-auto-columns:1fr`（或 flex 子项 `flex:1` + 父 `align-items:stretch`）让它们**自动等尺寸**，绝不靠手写不同 `width` 凑。
- **网格严格对齐**：多行多列节点一律用 `display:grid` 而非多个手排 flex。禁止用 `margin`/负偏移手动"挪"节点位置。
- **箭头/连线接在节点中轴**：横排流水线的箭头竖直居中对齐（`align-items:center`），竖排的箭头水平居中。
- **统一节奏**：全图同层 `gap` 一个值、节点 `padding` 一个节奏、所有块同一 `border-radius`（=本篇 `RADIUS` 档）；区与区间距 > 区内节点间距。
- **边缘对齐**：整张图各分区/各行左右边缘尽量对齐成一条线。
- 一句话：**看上去像用尺子摆过的——横平竖直、等大等距、边缘成线**。

**⑤ 强调唯一焦点（H0 彩色的主战场）**：全图**只留一个**最强视觉锚点。⛔ **不用实心深块+白字**；改用 **`--accent-bg` 柔和浅底 + `--text` 近黑深字 + `--accent` 稍粗边框(2px) + `font-weight:700`**。⛔ 焦点字别用 `--accent`（浅底上对比度不够），必须用近黑 `--text`。多个焦点 = 没有焦点。（TONE 0 纯线稿档：焦点不加彩底，改用更粗纯黑边 2.2px + 字重 800 突出。）

**⑥ 单位与符号规范**：数学符号用真 Unicode（`≤ ≥ σ ε ×` 而非 `<= >= sigma`），下标用 `f₁ f₂`；术语中英一致（首次出全称+缩写）。

**⑦ 密度平衡**：节点文字控制在 4–10 字 + 一行副标题；超长拆两行或移到 `.sub`。宁可多一个节点，不要一个节点塞两行长句。

> 一句话：**低饱和配色 + 字重层次 + 语义化连线 + 副标题密度 + 唯一焦点**——这五条齐了，图就有科研高级感。

### E 自检清单（设计前 + 出图后各过一遍）

**设计前自问：**
1. 这张图的逻辑流向能用一句话说清吗？
2. 按 A 节，我选的布局范式贴合这个逻辑吗？有没有硬凑判断/循环？
3. 它和本篇其它图的逻辑不同吗？（不同就该长得不同）
4. （A.1）节点里填的是这道题**特有的**方法/模型/判据，还是通用空词？后者立即改。
5. （A.1）这个方法**真实存在**的非平凡结构挖出来了吗？还是被我拉直成一根线了？

**出图后自检：**
1. 结构是否真实反映论文逻辑（方法名/步骤都是真的，无占位文字）？
2. 配色是否全部由 `H0` 按 B 节推导、协调低饱和、有意义色 ≤ 4？造型是否符合 `TONE`？
3. 是否满足 0 节**全部**硬约束（`fit-content` 收缩、**画布 `transparent`**、无 absolute、无外链、无标题、单页、宽高比 ≤8:1）？
4. **（A.1 内核自检）遮住题目只看节点文字，能认出这是哪类课题、哪个方法吗？**
5. `html`/`body`/`.fig` 有没有残留 `background:#fff`/`#fafafa`/带色底？有就改 `transparent`。
6. **（D.1 高级感）**字重层次拉开了吗？连线语义化了吗？每个节点有副标题吗？全图有且只有一个焦点吗？
7. 与本篇已生成的图相比：配色/造型统一，但结构因逻辑而不同？
8. **（造型旋钮 + LAYOUT 拓扑）** 圆角/连线/强调条/分区框是否按本篇 `RADIUS`/`ARROW`/`NODEACC`/`SECT` 落实、全篇一致？逻辑有多个等价范式时是否按 `LAYOUT % 候选数` 选的骨架？
9. ⛔ **（D.1 ④ 对齐硬纪律）眯眼看整张图：并列节点等大吗？行列对齐成线吗？边缘齐吗？箭头接在中轴吗？间距均匀吗？**
10. **（风格族 G 节）** 字体族对不对（A/C 衬线 / B 无衬线）？A 族有没有混进灰底/圆角>2px/副标题/阴影？B 族有没有残留柔和阴影或满屏副标题？**C 族有没有残留任何彩色**？A/B 族的 `--ac`/`--acbg` 是否由本篇 `H0` 代入、没写死示例色？——全篇所有图必须同一 `STYLE_FAMILY`。

### F 造型旋钮落 CSS（⛔ 按 Step 1 种子值选一档，全篇统一；全是黑白造型、不加颜色）

这四个**造型旋钮**（RADIUS/ARROW/NODEACC/SECT）把**皮肤**拉开差异；**宏观骨架**的差异由 `LAYOUT` 与《骨架池》承担。按 Step 1 算出的值各选一档，写进 `:root`/对应类，**全篇所有图用同一组**：

**RADIUS（圆角，定 `--r`）**——节点/框统一用 `border-radius:var(--r)`：

| 值 | `--r` | 观感 |
|---|---|---|
| 0 | `0` | 直角，硬朗工程感 |
| 1 | `4px` | 微圆，克制 |
| 2 | `10px` | 明显圆角，柔和 |
| 3 | `999px`（仅小节点/标签）+ 大块 `14px` | 胶囊感 |

**ARROW（连线样式）**——所有流向连线统一：

| 值 | 画法 |
|---|---|
| 0 | 细实线 1px + 小实心箭头 `▶`（`border`+CSS 三角或 `→`） |
| 1 | 粗实线 2.5px + 大箭头，流向感强 |
| 2 | 点线 `border-style:dashed`/`dotted` + 箭头，轻盈 |
| 3 | 不画线，用 `›`/`▸` chevron 字符做节点间分隔（横排流水线尤佳） |

**NODEACC（焦点/类型节点的强调方式）**——**替代**"实心彩底"：

| 值 | 画法 |
|---|---|
| 0 | 纯描边：焦点节点 `border:2px solid var(--accent)` + 白/浅灰底 |
| 1 | 左竖条：`border-left:4px solid var(--accent)`，其余细灰边 |
| 2 | 顶横条：`border-top:3px solid var(--accent)`，其余细灰边 |

**SECT（分区/分组框法）**：

| 值 | 画法 |
|---|---|
| 0 | 无框：纯靠 `gap`/留白 + 一个小节标题分组 |
| 1 | 细虚线框：`border:1px dashed var(--n-line)` 圈住一组 |
| 2 | 左侧竖标签条：组左侧一条竖 `--n-bg2` 窄条写分区名 |

> ⛔ **四个旋钮只改"造型结构"，一律不加颜色**。⛔ 同篇统一：一篇里所有图同一组旋钮值，别逐图变。

### G 风格族（⛔ 最顶层维度，由 Step 1 的 `STYLE_FAMILY` 定，凌驾于同名旋钮，全篇统一）

`STYLE_FAMILY` 先把图分成**三大类观感**，再由族内的 `H0`/`TONE`/`LAYOUT`/`ARROW` 继续细分。⛔ **本节规定的维度（字体族/节点底色/圆角上限/阴影/副标题/分组框/边框/是否用彩色）由风格族说了算，与之冲突的旋钮档以族为准**；本节没规定的维度仍按前面各节在族内照常随机（⛔ 但 C 族强制零彩色，`H0` 不用）。

| 维度 | **A 朴素竞赛风**（`=0`） | **B 现代精致风**（`=1`） | **C 纯黑白线稿**（`=2`） |
|---|---|---|---|
| 字体族 | 衬线 `Times`/`SimSun` | 无衬线 `Segoe UI`/`雅黑` | 衬线 `Times`/`SimSun` |
| 节点底 | 纯白 `#fff` | 极淡灰 `#f6f7f9` | 纯白 `#fff` |
| 圆角 | 直角~2px（`RADIUS` 封顶 2px） | 微圆 5px（`RADIUS` 封顶 6px） | 直角 0px（⛔ 强制直角，`RADIUS` 忽略） |
| 阴影 | **无** | **无** | **无** |
| 副标题 `.sub` | **完全不用** | **仅关键节点**留一行 | **完全不用** |
| 分组框 | 黑 `dashed` 虚线框 | 浅灰 `solid` 圆角框 | 黑 `solid`/`dashed` 直角框 |
| 边框 | 深黑灰 `#2b2b2b` 1px | 灰 `#c4c9d0` 1px | 纯黑 `#1a1a1a` 1–1.4px |
| 彩色 | 焦点+是/否/回边用 `H0`（`--ac`/`--no`） | 焦点+语义连线，`H0` 克制点缀 | ⛔ **零彩色**：焦点靠更粗黑边(1.8px)+字重800 |

⛔ **A/C 族"做减法"是刻意的**：高级感来自**朴素**。别给它们偷偷加灰底/圆角/副标题/阴影/彩色。⛔ **C 族与 A 族的区别**：A 保留少量 `H0` 彩色；C **一点彩色都没有**，纯靠黑/灰/白 + 边框粗细 + 字重(400/600/800)分层次——最贴近纯手绘黑白框图、印刷/复印无损。

**G.1 A 朴素竞赛风 · `:root` 与基础节点骨架**（照抄，`--ac`/`--acbg` 用本篇实际 H0 代入）：

```css
html,body{margin:0;padding:0;width:fit-content;height:fit-content;background:transparent}
.fig,.fig *{font-family:"Times New Roman","SimSun","Songti SC","Microsoft YaHei",serif;
  -webkit-font-smoothing:antialiased;box-sizing:border-box}
.fig{width:fit-content;padding:26px 30px;background:transparent;
  --edge:#2b2b2b; --txt:#111; --line:#444;
  --ac:hsl(H0,42%,45%); --acbg:hsl(H0,40%,95%); --no:#b0402f}   /* --ac/--acbg 用本篇 H0 代入 */
.n{border:1px solid var(--edge);background:#fff;color:var(--txt);
  padding:9px 14px;font-size:14px;font-weight:500;text-align:center;
  border-radius:2px;line-height:1.4}                            /* 直角、白底、无阴影、无副标题 */
.n.focus{border:1.6px solid var(--ac);background:var(--acbg);color:var(--ac);font-weight:700}
.grp{border:1.3px dashed var(--edge);border-radius:3px;padding:11px 13px;
  display:flex;flex-direction:column;gap:9px;align-items:center}  /* 黑虚线分组框 */
```

**G.2 B 现代精致风 · `:root` 与基础节点骨架**（照抄）：

```css
html,body{margin:0;padding:0;width:fit-content;height:fit-content;background:transparent}
.fig,.fig *{font-family:"Segoe UI","Helvetica Neue",Arial,"Microsoft YaHei","Noto Sans SC",sans-serif;
  font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased;box-sizing:border-box}
.fig{width:fit-content;padding:26px 30px;background:transparent;
  --line:#c4c9d0; --txt:#20242b; --muted:#727880; --nb:#f6f7f9;
  --ac:hsl(H0,45%,42%); --acbg:hsl(H0,40%,95%); --no:#c25a48}    /* --ac/--acbg 用本篇 H0 代入 */
.n{background:var(--nb);border:1px solid var(--line);color:var(--txt);
  padding:9px 14px;font-size:14px;font-weight:600;text-align:center;
  border-radius:5px;line-height:1.35}                            /* 淡灰底、5px微圆、无阴影 */
.n .sub{display:block;font-size:10.5px;font-weight:400;color:var(--muted);margin-top:2px}/* 仅关键节点用 */
.n.focus{background:var(--acbg);border:1.6px solid var(--ac);color:var(--ac)}
.grp{background:#fbfbfc;border:1px solid #e3e6ea;border-radius:7px;padding:11px 13px;
  display:flex;flex-direction:column;gap:9px}                     /* 浅灰实线圆角分组框 */
```

**G.4 C 纯黑白线稿 · `:root` 与基础节点骨架**（照抄，⛔ 全程零彩色、无 `--ac`）：

```css
html,body{margin:0;padding:0;width:fit-content;height:fit-content;background:transparent}
.fig,.fig *{font-family:"Times New Roman","SimSun","Songti SC","Microsoft YaHei",serif;
  -webkit-font-smoothing:antialiased;box-sizing:border-box}
.fig{width:fit-content;padding:26px 30px;background:transparent;
  --edge:#1a1a1a; --txt:#111; --line:#333}                       /* ⛔ 无 --ac/--acbg：纯黑白 */
.n{border:1px solid var(--edge);background:#fff;color:var(--txt);
  padding:9px 14px;font-size:14px;font-weight:600;text-align:center;
  border-radius:0;line-height:1.4}                               /* 直角、白底、纯黑边、无阴影 */
.n.focus{border:1.8px solid #000;font-weight:800}                /* 焦点：最粗黑边+字重800，⛔ 不加彩底 */
.grp{border:1.2px dashed var(--edge);border-radius:0;padding:11px 13px;
  display:flex;flex-direction:column;gap:9px;align-items:center} /* 黑虚线直角分组框 */
```

⛔ **C 族判定/分支/回边也全用黑**：把 G.3 里的 `var(--ac)`/`var(--no)` 一律换成 `#1a1a1a`。层次全靠**边框粗细 + 字重**，不靠颜色。

**G.3 三族共用的连线 / 判定 / 循环回边**（判定用圆角矩形不用菱形、回边用虚线示意）：

```css
/* 竖直箭头：细线 + CSS 三角 */
.dn{display:flex;flex-direction:column;align-items:center}
.dn .ln{width:1px;height:19px;background:var(--line)}
.dn .tp{width:0;height:0;border-top:6px solid var(--line);
  border-left:4px solid transparent;border-right:4px solid transparent}
/* 判定节点：圆角矩形 + --ac 边（⛔ 禁旋转菱形）；下接是/否分支 */
.n.dec{border:1.6px solid var(--ac);border-radius:6px;font-weight:600}
.branch{display:flex;align-items:flex-start;gap:44px}
.path{display:flex;flex-direction:column;align-items:center}
.lbl{font-size:12px;margin:2px 0}.lbl.no{color:var(--no)}
/* 循环回边：左侧虚线包边 + 竖排文字示意"回到上游" */
.loopwrap{display:flex;align-items:stretch}
.loopback{display:flex;align-items:center;border-left:1.4px dashed var(--no);
  border-top:1.4px dashed var(--no);border-bottom:1.4px dashed var(--no);
  border-radius:3px 0 0 3px;padding:0 7px;margin-right:8px}
.loopback .txt{writing-mode:vertical-rl;font-size:11px;color:var(--no);letter-spacing:1px}
```

⛔ **G.3 竖排回边文字禁塞公式**（`\(P_{t+1}\)` 之类）：KaTeX 渲染后会撑高被裁（真实翻车过）。回边文字用纯中文短语，公式留给横排节点。

**G.5 对齐骨架（⛔ 三族通用，防"参差/错位/大小不一"——照抄，别手写 width）**

⛔⛔ **对齐要"治本(grid) + 兜底(标记自检)"双保险**：①**治本**——对齐在写 HTML 时用下面的骨架从结构上保证；②**兜底**——给"本应对齐成一列/一行"的元素打 `data-mh-col="k"` / `data-mh-row="k"` 标记后，`--geom-check` 会**测量它们中轴坐标是否真对齐**(极差 >4px 判 FAIL、退出码1)。

```css
/* ① 一组并列节点(同一行或同一列)：必须放进同一个 grid 容器，自动等宽等高 */
.rowgrid{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:14px;align-items:stretch}
.colgrid{display:grid;grid-auto-flow:row;gap:12px;justify-items:stretch}
/* ② 多行多列矩阵：用 grid 显式列数，行列天然对齐(禁多个 flex 手排) */
.matrix{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;align-items:stretch;justify-items:stretch}
/* ③ 节点在 stretch 下自动等尺寸；文字多的靠内部换行，禁写不同 width 硬凑 */
.n{width:auto;min-width:0}          /* ⛔ 禁 width:120px 之类固定值；等宽交给 grid 的 1fr */
```

**三条硬规则（对应 D.1 ④，出图后眯眼再核一遍）**：
1. **并列必等尺寸**：任何"横排/竖排的一组同级节点"一律进 `grid` + `1fr`/`stretch`。
2. **行列必对齐**：多行多列一律 `display:grid`，禁止多个 `flex` 行手排。
3. **边缘必成线**：各分区/各行左右边缘对齐成一条线；箭头接节点中轴。
4. ⛔ **给对齐意图打标记**：主干/纵列上**每个应竖直对齐的节点 + 中间的竖箭头/连线**都加 `data-mh-col="1"`（同一列用同一个值）；**每个应水平对齐的同行节点**加 `data-mh-row="1"`。⛔ 只给"确实该对齐成一条线"的元素打。竖箭头是无文字的 `div` 也照打。**标记不影响渲染观感**，只为让确定性自检生效。

```html
<div class="colgrid">
  <div class="n" data-mh-col="1">① 数据预处理</div>
  <div class="v-arrow" data-mh-col="1"></div>   <!-- 竖箭头无文字也打，验证接中轴 -->
  <div class="n" data-mh-col="1">② 特征建模</div>
  <div class="v-arrow" data-mh-col="1"></div>
  <div class="n" data-mh-col="1">③ 求解验证</div>
</div>
```

⛔ **G 节收尾自检**：出图前确认——① 字体族对不对 ② A 族有没有混进灰底/圆角>2px/副标题/阴影 ③ B 族有没有残留柔和阴影或满屏副标题 ④ **C 族有没有残留任何彩色** ⑤ A/B 族的 `--ac`/`--acbg` 都由本篇 `H0` 代入、没写死示例色。有一条不符 = 风格族没落实，改。
