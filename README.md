# goal修复

> 本文件是 `F:\DeepSeekHarness` 的本地改造维护台账，不是 DeepSeek Harness 官方 README。
>
> 最后更新：**2026-08-18 20:05:00 +08:00（北京时间）**  
> 官方兼容基线：**DeepSeek Harness `0.1.0-rc.7`**  
> 本地模式：**`mathmodel`**  
> 维护原则：**Everything is a Plugin；不修改官方包，不把本地改造混入官方源码。**

## 1. 本文件的用途

本 README 只记录用户在官方 DeepSeek Harness 之外增加或改造的内容，目的是：

1. 明确本地修改的唯一来源，避免后续忘记改过什么。
2. 更新官方 Harness 前知道必须备份哪些文件。
3. 更新后只重新接入本地插件、Preset、Skill 和 Profile patch，避免旧文件覆盖新版官方实现。
4. 出现兼容问题时能够快速停用本地插件，而不是删除整个工作区。

详细插件开发与扩展说明见 [`plugins/dsh-mathmodel/README.md`](plugins/dsh-mathmodel/README.md)，完整需求、任务和验收证据见 [`Overall-goal/goal-1/`](Overall-goal/goal-1/) 与 [`Overall-goal/goal-2/`](Overall-goal/goal-2/)。

## 2. 官方范式与不可越界范围

本项目严格采用 DeepSeek Harness 的插件组合范式：

- 功能实现放在外置插件 `plugins/dsh-mathmodel/`。
- 模式定义放在用户级 Preset `.dsh/.agent-presets/mathmodel/`。
- Skill 的卡片声明与 Skill 同目录存放，不在 Client 中硬编码卡片列表。
- Web 端只通过 `.dsh/profiles/web/cordis.patch.yml` 挂载插件。
- Profile 依赖使用 `file:../../../plugins/dsh-mathmodel` 指向外置插件。
- 官方 `standard` 能力保持完整，`mathmodel` 只在其上增加专用 Persona 和工具。

以下内容视为官方或可再生成区域，**禁止手工合并本地逻辑**：

- `.dsh/profiles/**/node_modules/`
- 官方内置 Preset、官方插件源码和全局安装目录
- `plugins/dsh-mathmodel/lib/`：由 `npm run build` 从 `src/` 生成，不是修改源
- 依赖缓存、包管理器 store、浏览器缓存和临时构建目录

官方升级时不得把旧 `node_modules`、旧官方 Preset 或旧官方 bundle 整目录复制到新版。正确做法是保留本地源码，重新安装 Profile 依赖，再通过测试确认兼容。

## 3. 本地改造清单

### 3.1 外置 Mathmodel 插件

本地源码：`plugins/dsh-mathmodel/`

主要增加：

- `mathmodel` 模式的 Host、Client 和严格版本门。
- `/skill` 卡片、严格 schema、动态扫描、缓存失效和 Prompt 渲染。
- 卡片确认后只写入可编辑草稿，禁止自动发送。
- 右上角可收缩 Skill 说明目录：动态覆盖 `.dsh/skills` 全目录，支持搜索、单项展开、ARIA 状态、`Escape` 关闭和焦点返回。
- Python、LaTeX、Draw.io、Poppler 等依赖的只读预检。
- `vision_analyze` 与受控 `image_generate` 工具。
- 四类受管凭据与普通供应商设置。
- 单元测试、环境测试和真实 Draw.io/XeLaTeX 论文 E2E。

维护时修改 `src/`、`test/`、`scripts/` 和插件 README；修改源码后必须执行 `npm run build`，不要直接编辑 `lib/`。

### 3.2 用户级 Mathmodel Preset

本地目录：`.dsh/.agent-presets/mathmodel/`

该 Preset 以官方 `standard` roster 为基础，只增加数学建模 Persona 和专用工具。官方升级后必须重新比较 `standard` roster；不能继续复制旧 roster，也不能用本地版本覆盖新版官方 Preset。

### 3.3 Web Profile 接线

本地接线文件：

- `.dsh/profiles/web/package.json`
- `.dsh/profiles/web/cordis.patch.yml`
- `.dsh/profiles/web/pnpm-lock.yaml`（依赖解析记录）

接线职责：

- 通过本地 `file:` 依赖安装 `@deepseek-harness/dsh-mathmodel`。
- 禁用会与卡片 Source 重复注册的官方 `ui-skill` 行。
- 只挂载一次外置 `dsh-mathmodel` 插件。
- 通过 npm 依赖 + bundle 自激活挂载第三方 `dsh-plugin-subscriptions`（ChatGPT/Claude/Grok 订阅 OAuth 登录，详见 3.5 节），本地 patch 层仅做 `providers` 配置覆盖。
- 通过 GitHub 依赖 + bundle 自激活挂载第三方 `dsh-llm-oauth`（ChatGPT/Codex 订阅 OAuth 登录，详见 3.3b 节），本地 patch 层仅做 `catalog` 配置覆盖；`ui-skins` 同样改为 bundle 层自激活（`dsh plugin` 的 reconcile 按依赖声明自动维护 bundles，patch 层不再手工 insert）。

官方升级后应根据新版 Profile 重新应用最小 patch，禁止用旧 `cordis.patch.yml` 整体覆盖新版配置。

### 3.3a 第三方订阅插件 dsh-plugin-subscriptions

来源：`https://github.com/V1ki/dsh-plugin-subscriptions`（npm `0.3.1`，MIT），官方安装命令 `dsh plugin --profile web add dsh-plugin-subscriptions`。

- 功能：把 ChatGPT (Codex)、Claude、Grok (X Premium) 订阅作为 LLM provider，Settings → 订阅页 OAuth 登录，token 存 `~/.dsh/plugins/subscriptions/auth.json`（0600，自动刷新）。
- 接入方式：npm 预构建包（作者源码构建依赖其本机路径，本地不可构建）；bundle 层自激活，node 半边 `llm-subscriptions`、client 半边经 `dsh.client` 声明自动发现。
- **已知冲突与处置**：其 codex 路由启动时注册全局工具 `image_generate`，与本地 `mathmodel-tools` 的 API 生图工具同名（bundle 层先加载，后注册方启动失败）。处置：`cordis.patch.yml` 中对 `llm-subscriptions` 覆盖 `providers: [claude, grok]`，禁用 codex 路由以保留本地生图工具；UI 三个登录卡片仍全部显示，但 Codex 登录后模型不会进入选择器。ChatGPT 订阅生图已由 3.3b 节的原生 `codex-subscription` 连接解决，无需再启用其 codex 路由。
- peerDependencies `^0.1.0-rc.5` 与 rc.7 基线兼容；与本地三插件（mathmodel、mathmodel-tools、ui-skins）UI 注入点无重叠。
- **Grok 模型目录覆盖**（GOAL-44 引入）：本机网络无法访问 `cli-chat-proxy.grok.com`（自动发现 ECONNRESET），未覆盖时全部 Grok 模型回退插件默认 256k 窗口。处置：`cordis.patch.yml` 对 `llm-subscriptions` 覆盖 `models.grok`，7 个模型 `contextWindow` 均取 xAI 官方 `api.x.ai/v1/models` 实测返回的 `context_length`（grok-4.20 系/4.3 = 1M、grok-4.5/4.6 = 500k、grok-build-0.1 = 256k）；配置后插件关闭自动发现，直接采用该目录。`inputModalities: [text, image]` 为插件 zod schema 必填项，缺失会导致服务启动失败。
- **Grok 订阅生图**（GOAL-45 引入）：本插件的 Grok 登录凭据（`plugins/subscriptions/auth.json`）除聊天路由外，另被 `dsh-mathmodel` 的第六类生图连接 `grok-subscription` 复用（xAI 官方 Images API），详见 3.3b 节末条。

### 3.3b 订阅 OAuth 插件 dsh-llm-oauth 与原生 ChatGPT 订阅生图连接

来源：`https://github.com/ziyou979/dsh-llm-oauth`（GitHub `0.2.0`，MIT），安装命令 `dsh plugin --profile web add github:ziyou979/dsh-llm-oauth`（git 依赖需在 `pnpm-workspace.yaml` 的 `allowBuilds` 放行其 prepare 构建）。

- 功能：纯 LLM 路由插件，提供 Settings → OAuth / 订阅页的 ChatGPT (Codex)、xAI、Copilot、Anthropic、OpenRouter OAuth 登录；凭据写入 `$DSH_HOME/pi-ai-oauth.json`（pi-ai 格式，token 自动刷新）。默认休眠（`providers` 为空，登录后才注册聊天路由），**不注册任何工具**，与本地 `mathmodel-tools` 的 `image_generate` 零冲突。
- 本地配置：`cordis.patch.yml` 对 `llm-oauth` 覆盖 `catalog: [openai-codex]`——OAuth 页只显示 ChatGPT 登录；Claude/Grok 订阅登录仍由 3.3a 节的 `llm-subscriptions` 负责，两插件分工互补。
- **原生第五类生图连接 `codex-subscription`**（GOAL-42 引入）：`dsh-mathmodel` 生图模型区新增"ChatGPT 订阅"模板，固定走 `https://chatgpt.com/backend-api/codex/images/generations`（`gpt-image-2`），凭据复用 `pi-ai-oauth.json` 的 `openai-codex` 条目（读-改-写只替换该条目；<5 分钟预刷新 + 401 强刷重试一次），无需 API Key/Base URL，UI 引导到 OAuth 页登录。**注意：非官方支持端点，存在账号限制风险**；参考图不支持（明确报错），count>1 循环单图请求。
- 安全边界：token 只落 `$DSH_HOME/pi-ai-oauth.json`，源码/仓库/归档零凭据；`describeCodexCredential` 只返回登录状态布尔值。
- **原生第六类生图连接 `grok-subscription`**（GOAL-45 引入）：生图模型区新增"Grok 订阅"模板，固定走 xAI 官方 Images API `https://api.x.ai/v1/images/generations`（模型 `grok-imagine-image` / `image-2.0` / `image-quality`），凭据复用 3.3a 节 `llm-subscriptions` 的 Grok 登录（`plugins/subscriptions/auth.json`，读-改-写只替换 grok 条目，<5 分钟预刷新 + 401 强刷重试一次），无需 API Key/Base URL，UI 引导到订阅页登录。生图额度随 X Premium 订阅；参考图不支持（明确报错），count>1 循环单图请求，返回 `b64_json`/`url` 均可解析；token 只落订阅插件的 auth.json，源码/仓库/归档零凭据。

### 3.4 十二个手动 Skill 与卡片

下列 Skill 增加了 `mathmodel-card.yml`，并保持 `disable-model-invocation: true`、`user-invocable: true`，只能由用户手动触发：

| Skill | 本地改造用途 |
|---|---|
| `math-paper-cn` | 中文数学建模论文一键流程与结构化卡片参数 |
| `math-paper-huashu` | 华数杯模板、门禁和结构化卡片参数 |
| `math-paper-huawei` | 华为杯（研究生数模）GMCMthesis 模板、门禁（正文大于 25 页硬约束）、2023/2024 优秀论文参考与结构化卡片参数 |
| `grill-with-docs` | 面向新手的赛题思路启发与关键问题拷问 |
| `grill-ai-review` | 三名专项评委加一名后置主审 |
| `ai-draw-skills` | 科研配图分析、提示词和四类凭据状态 |
| `py-nature` | Nature 风格数据图与柱状图/三维图策略 |
| `humanizer` | 定位 AI 痕迹聚集段并按授权局部处理 |
| `research-writing-skill` | 中文论文润色并保护术语、公式与引用 |
| `claude-vision-skill` | 调用 DSH 原生视觉工具和百炼主备模型 |
| `anti-autoresearch` | 按证据等级提示论文诚信风险，不直接定性造假 |
| `imagegen` | 原生生图工具调用与连接级凭据（GOAL-16 引入） |

卡片协议为 `dsh.mathmodel.card/v1`。以后新增合规 Skill 时，应在 Skill 同目录增加 sidecar，不要修改 Client 中的列表。

Skill 说明协议为 `dsh.mathmodel.skill-help/v1`。说明目录会扫描 `.dsh/skills/*/SKILL.md`；当前 18 项均有人工通俗说明，未来新增 Skill 即使尚未补充人工文案也会显示兜底说明，不会从目录中消失。

### 3.5 凭据与旧配置边界

受管凭据引用：

- `DASHSCOPE_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `CUSTOM_IMAGE_API_KEY`

Key 不得写入 README、Prompt、普通设置、日志或错误报告。`claude-vision-skill` 目录中可能存在旧 `.env`；本地插件和改造后的 Skill 均不读取、复制、移动、改写或删除它。是否清理由用户在新配置验证成功后自行决定。

### 3.6 目标、证据与非生产目录

- `Overall-goal/goal-1/`：需求、设计、任务、状态、三轮审查和验收证据。
- `.dsh/计划文档/需求文档.md`：本次改造的原始规格。
- `.dsh.failed-expanded-copy-20260814/`、`.dsh.failed-junction-copy-20260814/`：失败复制操作留下的隔离记录，不参与运行，也不得当作新版 `.dsh` 合并来源。
- `.tmp-anti-autoresearch-source/`、`.playwright-cli/`：临时来源或验收目录，不是产品源码。

临时目录是否删除应由用户单独确认；官方升级时不要把它们复制回活动配置。

### 3.7 官方关键 UI 行为适配（升级高风险）

> **重要：本节属于官方关键行为覆盖清单。官方 Harness 升级前后必须逐项复核，不能按普通 CSS 修改处理。**

本地插件虽然没有直接编辑官方安装目录，但会在运行时改变官方会话日志按钮的呈现与无障碍属性：

| 官方关键点 | 官方当前结构/行为 | 本地运行时适配 | 升级风险 |
|---|---|---|---|
| Header utilities 插槽 | `data-slot="conversation.session.header.utilities"` | 仅在该插槽内查找会话日志按钮 | 插槽改名后适配失效 |
| Session log 按钮 | CSS Module 类名保留 `_sessionLogButton` 语义后缀 | 使用 `button[class*="_sessionLogButton"]` 精确匹配 | 官方改类名或改为非 button 后失效 |
| Session log 文案 | 按钮内含 `<span>Session log</span>` 与官方下载 SVG | 文案仅视觉隐藏，保留官方 SVG | 官方 DOM 层级变化后文字可能重新出现或图标尺寸异常 |
| 无障碍名称 | 官方当前按钮没有稳定中文 `aria-label/title` | Mathmodel 挂载时设为“下载会话日志”，卸载时恢复原值 | 生命周期变化可能导致属性未恢复 |
| 顶部布局 | 官方按钮当前为 36px 高，`y=12px` | 技能说明按钮按同尺寸、同顶边、8px 间距定位 | 官方标题栏高度、右边距或按钮尺寸变化后可能碰撞 |

实现位置：`plugins/dsh-mathmodel/src/client-bundle.cjs` 中以下三处：

1. `[data-slot="conversation.session.header.utilities"] > button[class*="_sessionLogButton"]` 的图标化 CSS。
2. `MathmodelInfo` 内为官方按钮设置并恢复 `aria-label/title` 的 `React.useEffect`。
3. `.dsh-mm-info-launcher` 与 `.dsh-mm-info` 的同排按钮及抽屉定位。

此适配的性质是：**不改官方源码，但覆盖官方关键 UI 的运行时显示和属性，因此属于强兼容耦合。** 官方升级后，在重新启用 Mathmodel 插件前，必须先验证上述选择器仍唯一命中会话日志按钮；禁止为了“让样式继续生效”而放宽为全局 `button`、任意 SVG 或不带 utilities 插槽的选择器。

### 3.8 Windows 快捷启动器（npm 更新覆盖风险）

本机快捷入口实际执行：

```text
%APPDATA%\npm\dsh-assets\启动-DeepSeek-Harness.ps1
```

该文件位于 npm 全局资产目录，不属于官方源码，也不在本工作区内，但重新安装或升级全局 DSH 时可能被覆盖。当前本地改造：

- `DSH_HOME` 固定为 `F:\DeepSeekHarness\.dsh`，工作目录固定为 `F:\DeepSeekHarness`。
- 若 3080 已监听，立即复用现有服务，不重复启动；实测无浏览器模式 562ms 返回。
- 冷启动绕过 `dsh.cmd` 和 Windows Terminal，直接以 `node.exe + dsh/lib/bin.js` 隐藏启动，避免黑色终端窗口。
- 启动轮询由 15 秒放宽到 45 秒，100ms 检查一次；真实冷启动约 23.6 秒，不再提前误报失败。
- 服务日志写入 `%LOCALAPPDATA%\DeepSeekHarness\logs\web.stdout.log` 和 `web.stderr.log`。
- 仅在端口就绪后打开 `http://127.0.0.1:3080`；失败弹窗会显示 stderr 尾部与日志路径。
- 支持维护测试参数 `-NoBrowser`，用于验证启动而不额外打开浏览器标签页。

官方/npm 升级后必须检查该脚本是否仍存在、`dsh/lib/bin.js` 路径是否变化，并重新执行冷启动与已启动复用测试。禁止把旧的整个 npm 全局目录覆盖到新版；只根据新版入口最小重做本脚本。

## 4. goal 修复记录

所有时间均为北京时间（UTC+08:00）。后续每次修改必须追加记录，禁止改写历史记录。

### GOAL-20260814-01：创建 Mathmodel 外置模式

- 时间：**2026-08-14 18:30—19:23 +08:00**
- 原因：在不修改官方包的前提下增加数学建模专用模式。
- 修改：建立外置插件、版本门、用户 Preset、Web Profile 本地依赖和最小 Cordis patch。
- 主要文件：`plugins/dsh-mathmodel/`、`.dsh/.agent-presets/mathmodel/`、`.dsh/profiles/web/package.json`、`.dsh/profiles/web/cordis.patch.yml`。
- 官方冲突面：Remote、Slot、Input Trigger、Conversation、Preset roster 和 `ui-skill` 注册行为。
- 验证：离线安装、Peer 检查、dump-config、Web 启动和版本失败关闭通过。
- 回滚：在 `cordis.patch.yml` 中重新启用官方 `ui-skill` 并禁用 `dsh-mathmodel`，随后重启 Web。

### GOAL-20260814-02：集成数学建模 Skill 与安全工具

- 时间：**2026-08-14 19:00—20:09 +08:00**
- 原因：将论文、赛题启发、评审、绘图、润色、视觉和诚信审查统一接入手动卡片流程。
- 修改：增加十张 sidecar；最小修改目标 Skill；加入预检、视觉、生图、凭据和供应商设置；论文流程接入 Goal/PDF 门禁。
- 主要文件：`.dsh/skills/<目标 Skill>/SKILL.md`、同目录 `mathmodel-card.yml`、`plugins/dsh-mathmodel/src/`。
- 安全边界：零自动发送、零 Key 回显、零 `.env` 加载、付费生图必须同时满足凭据、健康检查、数量上限和用户授权。
- 验证：插件测试、两套论文 Skill 测试和真实 Draw.io/XeLaTeX E2E 通过。
- 回滚：保留 Skill 文件，只停用外置插件；不得删除整个 `.dsh/skills`。

### GOAL-20260814-03：修复 Web Remote 与 Skill 说明面板

- 时间：**2026-08-14 19:23—20:01 +08:00**
- 原因：真实浏览器发现 Remote 子命名空间挂载顺序和结果信封处理错误，同时需要 Codex 风格右上角说明面板。
- 修改：先挂载再解析 Remote；统一解包 `Result`；增加右上角持久入口、展开/折叠、ARIA、`Escape` 关闭和焦点返回。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、Remote 描述符与相关测试。
- 验证：`/math-paper-cn` 卡片、普通 Skill、零发送草稿、非空会话保护和说明面板浏览器 E2E 通过，控制台错误为 0。
- 回滚：恢复上一版插件源码并重新执行 `npm run build`，不要修改官方 Client bundle。

### GOAL-20260814-04：参数卡片极简重设计

- 时间：**2026-08-14 20:13—20:23 +08:00**
- 原因：旧卡片内容高 817px，在 1280×720 视口中顶边达到 -180px，标题被裁切，复选框与标签分离且留白失控。
- 修改：卡片收窄至 680px；固定在可视区；控件统一为 38px；使用 18px 列距和 12px 行距；布尔项改为横向选择行；操作区固定在卡片底部。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/design-qa.md`、`Overall-goal/goal-1/evidence/task-025/`。
- 验证：同视口前后截图、底部滚动状态、复选框、下拉框、Skill 面板、`Escape` 和浏览器控制台检查通过；Design QA 为 `passed`。
- 回滚：恢复本地插件上一版本的卡片 CSS 与标记并重新构建；不涉及官方样式文件。

### GOAL-20260814-05：补全本地维护台账

- 时间：**2026-08-14 20:32:38 +08:00**
- 原因：原根 README 只有启动说明，无法支持官方升级前的本地改造识别、备份、重接线和回滚。
- 修改：补充官方/本地边界、改造清单、带时间的 goal 记录、升级保护流程、验证命令、回滚流程和后续记录范式。
- 主要文件：`README.md`。
- 验证：UTF-8、标题唯一性、路径存在性和 Markdown 结构检查。
- 回滚：仅恢复本 README 的上一版本，不影响运行代码。

### GOAL-20260814-06：全量 Skill 说明目录极简重设计

- 时间：**2026-08-14 20:48—20:54 +08:00**
- 原因：旧说明面板一次只展示单个 Skill，内容纵向堆叠过长，无法快速了解 `.dsh/skills` 中的全部能力。
- 修改：新增动态 Skill 说明目录和 `mathmodelCards.help` Remote；覆盖当前 15 个 Skill；加入搜索、单项展开、当前项高亮、窄屏抽屉、`Escape` 焦点返回；移除冗余“调用”详情。
- 主要文件：`plugins/dsh-mathmodel/src/cards/registry.js`、`src/cards/remote.js`、`src/host.js`、`src/typert-shared.js`、`src/client-bundle.cjs`、相关测试与 `design-qa.md`。
- 官方冲突面：只使用外置插件 Remote 与 Slot，不修改官方 Client、官方 Skill 或官方样式。
- 验证：当前目录 15/15 覆盖，搜索“论文”8 项，清空恢复 15 项，单项展开、收起、焦点返回和 408px 窄屏通过；`npm run check` 与 64/64 测试通过；Design QA 为 `passed`。
- 回滚：恢复上述外置插件源码与构建产物并重启 Web；无需改动 `.dsh/skills` 或官方包。

### GOAL-20260814-07：修复 Skill 说明入口与原生按钮重叠

- 时间：**2026-08-14 20:56—20:59 +08:00**
- 原因：浮动“技能说明”入口固定在 `top: 12px`，侵入 Harness 原生标题栏，在会话标题较长或窄屏环境下会与 `Session log` 等原生按钮重叠。
- 修改：入口移到原生标题栏下方，桌面使用 `top: 64px`、窄屏使用 `top: 58px`；抽屉分别从 `108px`、`102px` 开始；入口固定最小高度 36px，入口与抽屉始终保留至少 8px 间距，并限制窄屏最大宽度。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/test/client-panel.test.mjs`、`Overall-goal/goal-1/evidence/task-027/`。
- 官方冲突面：只调整外置插件浮动入口和抽屉坐标，不修改 Harness 原生标题栏、按钮或样式。
- 验证：1280×720 实际页面中入口与 `Session log` 矩形相交数为 0；入口底边 100px、抽屉顶边 108px，间距 8px；静态回归同时锁定桌面和 760px 以下窄屏区间；`npm run check` 与 65/65 测试通过。
- 回滚：恢复本地插件中本记录对应的四处定位值并重新构建、重启 Web；不涉及官方文件。

### GOAL-20260814-08：顶部操作改为 Codex 式同排图标

- 时间：**2026-08-14 21:01—21:10 +08:00**
- 原因：用户希望参照 Codex 顶部工具栏，把“技能说明”和会话日志下载放在同一水平行，并去掉占空间的文字按钮。
- 修改：“技能说明”改为 36×36 的目录图标按钮；官方 `Session log` 通过稳定的 utilities 插槽与 `_sessionLogButton` 语义后缀精确适配为仅下载图标；两个按钮同为 `y=12px`、高度 36px、水平间距 8px；说明抽屉从 `top=56px` 开始，与按钮行保持 8px。
- 可访问性：两个图标按钮分别保留 `aria-label/title`“技能说明”和“下载会话日志”；官方文字使用视觉隐藏而非删除，键盘与读屏名称不丢失。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/test/client-panel.test.mjs`、`Overall-goal/goal-1/evidence/task-028/`。
- 官方冲突面：不修改官方源码；只在外置插件运行时匹配 `conversation.session.header.utilities` 中的会话日志按钮，卸载插件即可恢复原样。
- 验证：1280×720 实测两按钮均为 36×36、顶边同为 12px、水平间距 8px、碰撞为 0；展开后入口与 400px 抽屉间距 8px；收起/展开截图、ARIA、tooltip、`npm run check` 和 65/65 测试均通过。
- 回滚：恢复外置插件中图标标记、utilities 适配 CSS 和定位值，重新构建并重启 Web；不需要恢复官方文件。

### GOAL-20260814-09：登记官方关键 UI 覆盖与升级风险

- 时间：**2026-08-14 21:12:21 +08:00**
- 原因：GOAL-08 不只是普通视觉调整；它在运行时覆盖官方 `Session log` 按钮的文案呈现、尺寸及 `aria-label/title`，必须作为官方关键行为适配独立管理。
- 修改：新增“3.7 官方关键 UI 行为适配（升级高风险）”，登记官方插槽、语义类名、DOM 层级、SVG、无障碍属性和标题栏几何依赖；补充升级前检查和定向回滚规则。
- 主要文件：`README.md`。
- 风险级别：**高**；官方 Web Header、Session log 或 CSS Module 结构变化时必须先禁用本地适配并重新验收。
- 验证：README 唯一标题、GOAL-09 唯一记录、关键选择器/恢复语义/升级步骤均存在。
- 回滚：仅回滚本次文档补充不会改变运行行为；若要回滚官方按钮覆盖，按第 8 节“仅回滚官方 Session log 覆盖”执行。

### GOAL-20260814-10：修复 Windows 快捷启动误报与黑色终端

- 时间：**2026-08-14 21:24—21:30 +08:00**
- 原因：旧启动器通过 `dsh.cmd` 拉起 Windows Terminal，并只等待 15 秒；本机真实冷启动超过阈值时，服务随后成功，但启动器已经弹出“服务启动失败”。
- 修改：工作目录改为项目根；直接隐藏启动 Node/DSH 入口；轮询改为 100ms、最长 45 秒；已运行服务立即复用；增加 stdout/stderr 日志和 `-NoBrowser` 验收参数。
- 主要文件：`%APPDATA%\npm\dsh-assets\启动-DeepSeek-Harness.ps1`、`README.md`、`Overall-goal/goal-1/evidence/task-029/`。
- 官方冲突面：启动器依赖全局 npm 中的 `@deepseek-ai/dsh/lib/bin.js` 路径，升级或重装 DSH 后可能被覆盖或失效。
- 验证：PowerShell 语法错误 0；已运行服务复用 499—562ms 且 PID 不变；真实冷启动约 23.6 秒，3080 HTTP 200、首个复查请求 87ms、stderr 0 字节；启动进程为隐藏的直接 Node，无 Windows Terminal 子进程；旧失败弹窗进程已定向关闭。
- 回滚：恢复旧脚本会重新引入 15 秒误报和 Terminal 窗口；推荐按第 3.8 节根据新版 DSH 入口重建，而不是复制旧 npm 目录。

### GOAL-20260814-11：将生图模型配置迁入模型设置页

- 时间：**2026-08-14 22:07:15 +08:00**
- 原因：`/ai-draw-skills` 参数卡同时承载论文配图参数与四组供应商凭据，信息密度过高；自定义供应商只显示 Key、缺少 Base URL 与模型名，也容易让用户误以为当前对话模型会直接承担生图。
- 修改：在官方“设置 > 模型”内容区末尾增量挂载插件自有的“生图模型”区域；提供百炼、OpenAI、Gemini、自定义四行供应商状态与折叠编辑，自定义项完整包含 Base URL、模型名和受管 Key。标准供应商明确使用适配器内置官方接口，仅编辑模型名和 Key。`/ai-draw-skills` 卡片移除四个凭据输入，改为指引到统一设置入口。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`.dsh/skills/ai-draw-skills/mathmodel-card.yml`、`plugins/dsh-mathmodel/test/client-panel.test.mjs`、`plugins/dsh-mathmodel/test/first-party-cards.test.mjs`、`plugins/dsh-mathmodel/test/card-snapshots.json`、`design-qa.md`、`README.md`。
- 官方冲突面：本地插件通过当前“模型/Models”标题定位官方模型 Section，并在其末尾创建插件挂载节点；官方若改名、改 DOM 层级或为模型 Section 增加正式子 Slot，需要重新适配并优先迁移到官方 Slot。没有替换或修改官方 `settings.section` 的 `models` 贡献，也没有写入官方聊天模型配置。
- 安全边界：API Key 继续只经 DSH 受管凭据 Remote 写入，不进入 Prompt、普通设置或 README；本次没有构建、热更新、重启、停止服务，也没有操作正在运行的论文任务。源代码将在下一次用户正常重启 Web 后生效。
- 验证：`npm run check` 通过；`node --test test/*.test.mjs` 共 **67/67** 通过。为保护正在运行的论文，本次未把新版 bundle 写入活动 Profile，浏览器视觉验收按 `design-qa.md` 标记为 blocked，待论文结束后的正常重启再完成同视口截图验收。
- 回滚：移除 `ImageProviderSettings`、`createImageProviderActions`、对应样式与第二个 `conversation.input.overlay` 贡献；把四个 `credential-status` 字段恢复到 `ai-draw-skills/mathmodel-card.yml` 并恢复快照。无需修改或回滚任何官方模型配置。
- 后续验收：**2026-08-14 23:10:23 +08:00** 论文任务结束后执行 `npm test`，构建 23 个插件文件且 **67/67** 测试通过；随后正常重启 Web，3080 返回 HTTP 200。真实浏览器确认四个生图供应商列表、自定义 Base URL/模型/Key 展开编辑、原生纵向滚动均正常，控制台 warning/error 为 0；`design-qa.md` 已更新为 `passed`。

### GOAL-20260814-12：论文卡片增加赛事语言与全文图片总量

- 时间：**2026-08-14 23:44:44 +08:00**
- 原因：原一键论文卡片固定使用中文，并以“每问 2 至 4 张”约束图片，无法覆盖英文赛事，也容易导致各问机械平均配图。
- 修改：`math-paper-cn` 与 `math-paper-huashu` 新增 `competition_language`，允许选择中文或英文；Prompt 和 Skill 工作流要求正文及所有图中文字统一采用所选赛事语言，并达到顶刊一区 Top 1 绘图标准。删除 `figures_per_question`，新增 `figure_total` 数字字段，默认 15、允许 1 至 40 自定义；全文按论证价值动态分配图片并严格核对总量，禁止重复凑图。
- 主要文件：`.dsh/skills/math-paper-cn/mathmodel-card.yml`、`.dsh/skills/math-paper-huashu/mathmodel-card.yml`、两套 Skill 的 `SKILL.md`、`AGENT.md`、`references/workflow.md`、`references/visual-style.md`、`references/auto-checklist.md`，以及 `plugins/dsh-mathmodel/test/first-party-cards.test.mjs`、`plugins/dsh-mathmodel/test/paper-skills.test.mjs`、`plugins/dsh-mathmodel/test/card-snapshots.json`、`README.md`。
- 官方冲突面：无官方模型或官方 UI 修改；仅改变本地卡片字段和两套本地论文 Skill 契约。旧项目若仍保存 `figures_per_question`，升级时应迁移为 `figure_total`，不可同时保留两套数量约束。
- 安全边界：`figure_total` 只控制最终入文图片总数；付费 AI 生图仍受 `ai_image_limit`、供应商健康和 `confirm_paid_calls=true` 三重门禁约束，不会因默认 15 张自动产生费用。
- 验证：`npm test` 构建 23 个插件文件且 **67/67** 测试通过；卡片严格 Schema 与 Prompt 快照通过；旧 `figures_per_question` 与“每问 2 至 4 张”约束检索结果为 0；运行中的 Web 保持 HTTP 200。
- 回滚：恢复两张卡片的 `figures_per_question`，移除 `competition_language` 与 `figure_total`，同步恢复两套 Skill/引用文件、测试夹具和 Prompt 快照；不涉及官方 Harness 文件。

### GOAL-20260814-13：修复生图工具工作区绑定并实测自定义端点

- 时间：**2026-08-14 23:57:08 +08:00**
- 原因：`image_generate` 与 `vision_analyze` 错误读取不存在的 `session.meta.cwd`，导致工具在访问供应商前报“需要绑定带工作区的 Agent 会话”。
- 修改：工作区来源改为 DeepSeek Harness 官方工具一致使用的 `exec.agent.session.header.cwd`，继续在缺少工作区时失败关闭；新增官方会话字段回归测试。
- 主要文件：`plugins/dsh-mathmodel/src/tools.js`、`plugins/dsh-mathmodel/test/tool-contracts.test.mjs`、`README.md`。
- 官方冲突面：依赖官方 Tool Exec 的 `agent.session.header.cwd`；官方若调整 Session Header 契约，需要与 `dsh-tool-fs`、`dsh-tool-pwsh` 同步适配。
- 安全边界：不回退到 `process.cwd()`，避免无工作区会话把图片写入错误目录；测试不输出或记录 API Key。
- 验证：构建 23 个插件文件，**68/68** 测试通过并正常重启 Web。使用已配置的自定义供应商执行 1 张最小真实生图请求，实际访问 `https://opencode.ai/zen/go/v1/images/generations`，返回 HTTP 404，未生成文件、未写入伪成功结果。OpenCode Go 官方文档仅声明 `/chat/completions`、`/messages` 与 `/models`，没有声明 `/images/generations`。
- 回滚：恢复旧字段会重新产生工作区绑定错误，不建议回滚；若官方升级改变 Header，仅定向调整 `workspaceOf()` 并保留失败关闭测试。

### GOAL-20260815-14：柱状图禁用策略改为源码级硬门禁

- 时间：**2026-08-15 16:39:21 +08:00**
- 原因：旧规则把“禁用”表述成只禁止普通柱状图，并按 manifest 图型名称排除 `interval`，没有扫描真实 Python 调用，导致时间区间图通过 `barh()` 绕过门禁。
- 修改：两套一次性论文 Skill 统一定义 `禁用=零例外`、`少用=同源完整 bar_exception`、`正常=按语义选图`；卡片草稿明确禁止常见柱形 API；门禁使用 Python AST 扫描 `bar/Bar`、`barh`、`broken_barh`、`barplot`、`mark_bar`、`vbar/hbar` 及 `kind="bar/barh"`，同时排除论文附录副本、赛题与文献参考代码，避免重复或无关误报。
- 主要文件：`plugins/dsh-mathmodel/src/cards/prompt.js`、相关 Prompt 测试/快照；`.dsh/skills/math-paper-cn/` 与 `.dsh/skills/math-paper-huashu/` 内的 `SKILL.md`、`AGENT.md`、绘图参考、柱状图门禁及专项测试。
- 官方冲突面：无官方源码或 UI 修改；仅改变本地卡片 Prompt 和两套本地论文 Skill 的 step3 门禁。旧项目重新初始化或升级门禁契约后，禁用策略下的历史柱形调用会按预期失败。
- 安全边界：未修改 `F:\数学建模赛题\25国赛-dsv4f` 的论文、代码或图片；门禁只读扫描项目 Python 源码，不执行绘图脚本，也不读取凭据。
- 验证：两套门禁测试分别 **40/40**、**51/51** 通过，插件构建与 **68/68** 测试通过；对旧工作区只读复测准确拦截 `Q3/solve_q3.py:132`、`Q4/solve_q4.py:124` 两处 `barh()`，不再误报文献参考代码。
- 回滚：只恢复两套 `check_python_bar_chart_policy.py`、对应规则文档与 `prompt.js` 的策略附加行，并同步恢复专项测试和三项 Prompt 快照；不需要回滚官方 Harness 或现有论文工作区。

### GOAL-20260815-15：柱状图门禁三轮全链路对抗加固

- 时间：**2026-08-15 16:56:23 +08:00**
- 原因：GOAL-14 已覆盖常见直接调用，但尚未对导入别名、赋值别名、动态 `getattr` 和 Plotly 字典式图型声明完成对抗验证，也未在修改后重跑真实论文 E2E。
- 修改：仅扩展两套 `check_python_bar_chart_policy.py` 的 AST 识别，补充 `from ... import bar as draw`、`draw=ax.bar`、`getattr(ax, "barh")`、调用参数 `type/mark="bar"` 与字典 `{"type/mark":"bar"}`；新增对应正反例，继续忽略注释、普通字符串、论文附录副本、赛题和文献参考源码。
- 主要文件：`.dsh/skills/math-paper-cn/scripts/checks/check_python_bar_chart_policy.py`、同目录 `test_python_bar_chart_policy.py`，以及 `.dsh/skills/math-paper-huashu/` 下对应两个镜像文件。
- 官方冲突面：无官方源码、插件 API、卡片 Schema 或 UI 修改；只加固本地论文 Skill 的源码扫描门禁。
- 安全边界：检测只读取 AST，不导入或执行被检项目代码；未修改 `F:\数学建模赛题\25国赛-dsv4f`，负向回归只读运行门禁。
- 验证：两套专项攻击矩阵各 **9/9**；中文论文完整门禁 **44/44**、华数杯完整门禁 **55/55**；插件语法检查和 **68/68** 测试通过；真实 Draw.io/XeLaTeX 论文 E2E 的 7 项检查全部通过并生成 17 页中文 PDF；旧项目仅准确拦截 Q3/Q4 两处 `barh()`；两套门禁 SHA-256 一致。
- 回滚：只恢复本记录涉及的两套门禁脚本和专项测试；GOAL-14 的直接调用检测、Prompt 与规则文档可独立保留。

### GOAL-20260815-16：原生 ImageGen Skill 与会话图片展示

- 时间：**2026-08-15 17:34:05 +08:00**
- 原因：原 `/ai-draw-skills` 仅规划提示词，普通 `standard` 会话也没有挂载 `image_generate`；即使设置页已有 Key、Base URL 与模型，Agent 仍可能检查环境变量或使用本地绘图，生成结果也缺少 DSH 原生附件投影，无法稳定在会话中显示。
- 修改：新增仅手动触发的 `/imagegen` Skill 与零发送配置卡片；新增从官方 `standard` roster 机械派生、只额外挂载 `mathmodel-tools` 的“标准生图模式”；`image_generate` 成功后将工作区文件存入官方附件服务，并通过原生 `image` content block 在工具结果中显示，模型侧只接收相对路径摘要；失败结果不渲染图片。卡片采用两列极简布局，支持供应商、比例、尺寸、数量、工作区参考图与单次付费授权。
- 主要文件：`.dsh/skills/imagegen/`、`.dsh/.agent-presets/imagegen/`、`plugins/dsh-mathmodel/src/tools.js`、`plugins/dsh-mathmodel/src/cards/registry.js`、`plugins/dsh-mathmodel/test/image-presentation.test.mjs` 及相关卡片、Preset、帮助与快照测试；规格记录位于 `openspec/`，设计验收位于 `design-qa.md`。
- 官方冲突面：依赖官方附件服务 `attachments.saveImage()`、通用工具结果卡的 `image` content block、Preset roster 与插件注入契约；未修改官方 `standard`、官方 Client、原模型设置或供应商配置。官方升级后需重新比较 `standard` roster，并复测附件引用的持久化与回放。
- 安全边界：Key、Base URL 与模型仅由既有受管设置读取，不进入 Prompt、会话或 README；勾选只授权当前一次付费调用；参考图限制在工作区且最多 4 张；本次验收未发起真实付费生图请求，也未改变现有供应商配置。
- 验证：插件语法/构建检查通过，插件全量测试 **72/72**；OpenSpec 严格验证通过；真实浏览器确认“标准生图模式”、`/imagegen`、零发送草稿注入、桌面/窄屏/移动布局和控制台 warning/error **0**。原生附件保存、相对路径脱敏、成功图片块与失败不展示图片均有确定性自动测试。`skill-creator` 通用校验器不识别 DSH 专用的 `user-invocable`、`disable-model-invocation` frontmatter，故以 DSH 卡片/目录/插件契约测试作为有效校验。
- 回滚：移除 `.dsh/skills/imagegen/` 和 `.dsh/.agent-presets/imagegen/`，再恢复本记录涉及的 `tools.js`、帮助注册及相关测试并重新构建；无需删除 Mathmodel 插件、修改官方 `standard` 或清除现有模型凭据。

### GOAL-20260815-17：ImageGen 默认保存到所选工作区

- 时间：**2026-08-15 18:30:07 +08:00**
- 原因：`/imagegen` 原先默认写入 `artifacts/generated-images`，与用户期望的当前所选工作区文件夹不一致。
- 修改：仅将卡片、Skill 说明、工具参数和服务端兜底的默认保存目录统一改为 `.`；仍可填写工作区内的自定义相对目录。
- 主要文件：`.dsh/skills/imagegen/mathmodel-card.yml`、`.dsh/skills/imagegen/SKILL.md`、`plugins/dsh-mathmodel/src/tool-contracts.js`、`plugins/dsh-mathmodel/src/image/service.js` 及对应测试快照。
- 官方冲突面：未修改官方源码、供应商、Key、模型配置、卡片布局或调用流程；仅调整本地 ImageGen 默认值。
- 安全边界：自定义目录仍必须位于当前工作区内，越界路径继续失败关闭。
- 验证：插件语法检查通过；全量测试 **72/72**，并验证省略 `outputDir` 时生成文件直接落入当前工作区根目录。
- 回滚：将上述四处默认值恢复为 `artifacts/generated-images`，更新卡片快照后重新构建。

### GOAL-20260815-18：Windows x64 完整便携发行版

- 时间：**2026-08-15 23:06:15 +08:00**
- 原因：数学建模工具链依赖宿主机 Node、Python、TeX Live、Draw.io 与 Poppler，无法作为净化后的开箱发行版迁移。
- 修改：新增相对路径启动、自检、可复现构建、运行时清单、秘密与固定路径扫描、ZIP 解压复测；插件及三套论文 Skill 优先使用包内依赖，严格模式禁止系统回退；中文和空格路径通过临时 `subst` 盘符兼容旧式 Windows 工具，服务退出后自动释放。
- 主要文件：`portable/`、三个根目录入口、`plugins/dsh-mathmodel/src/preflight.js`、三套论文 Skill 的 Draw.io/LaTeX 运行时脚本与字体模板、对应测试和 `Overall-goal/goal-2/`。
- 官方冲突面：升级 Harness、Web Profile 或论文模板后，需复核 CLI 参数、Profile 依赖物化、预检协议、TeX 宏包与字体回退；不修改官方安装包。
- 安全边界：发行版不含 Key、会话、论文和开发缓存；不要求管理员权限、不写注册表、不修改系统 PATH；在线模型仍需接收者自己的网络与凭据。
- 验证：staging 与 ZIP 解压自检通过；插件测试 **73/73**、环境测试 **1/1**、17 页真实论文 E2E、Python/CBC、Draw.io 三格式、三套 XeLaTeX、Poppler、中文空格路径离线启动 HTTP 200、端口身份识别与 `data/` 保留均通过。未在独立 Windows 10 干净虚拟机复测，保留该兼容风险。
- 回滚：保留上一份已验收 ZIP；仅替换 `app/` 与 `runtime/`，不要覆盖 `data/`。新版本失败时恢复旧 ZIP，并将原 `data/` 目录放回同级位置。

### GOAL-20260816-19：MetaMath Harness 本地品牌标记

- 时间：**2026-08-16 11:47:43 +08:00**
- 原因：统一桌面入口与数学建模模式的品牌识别，避免继续使用与本地功能无关的官方鲸鱼字标。
- 修改：桌面快捷方式改名为 `MetaMath Harness`，保留原启动目标与参数；新增“鲸鱼 + 曲线坐标轴 + 珊瑚节点”PNG 标记，并在 Web 左上角以 `MetaMath HARNESS` 锁定字标局部覆盖官方品牌区。
- 主要文件：`plugins/dsh-mathmodel/src/assets/metamath-brand-mark.png`、`src/client-bundle.cjs`、`scripts/build.mjs`、`test/client-panel.test.mjs` 与 `design-qa.md`；桌面快捷方式和图标文件位于用户本地 npm 资源目录，不纳入仓库。
- 官方冲突面：仅依赖官方侧栏品牌容器 `.hHd-Xa_logoRow` 与品牌按钮选择器；Harness UI 改版后需复核该局部挂载点。未修改官方包或 `node_modules`。
- 安全边界：图标为本地资产，未引入网络请求、凭据、遥测或外部资源；原生“新建会话”可访问名称与交互保持不变。
- 验证：插件语法检查与全量测试 **74/74** 通过；新页面加载无控制台 error，浏览器实测左上角标记为 28×28，官方 SVG 仅在该品牌区隐藏。
- 回滚：删除品牌注入和 `src/assets/metamath-brand-mark.png`，重新构建插件；桌面端将快捷方式重命名为 `DeepSeek Harness` 并恢复 `dsh-official.ico` 即可。

### GOAL-20260816-20：OpenCode RT 实时模型与受控识图

- 时间：**2026-08-16 14:40:57 +08:00**
- 原因：内置 `opencode-go` 模型目录随 DSH 安装包固定，无法及时反映 OpenCode Go 的最新模型；自定义模型未声明输入模态时，Harness 默认只接受文本，导致底层多模态模型也无法上传图片。
- 修改：在官方“添加提供方”的下拉菜单内注入 `OpenCode RT`，选择后仍使用同一张官方添加卡片填写 API Key；保存时从官方 `/models` 同步模型，并复用 `OPENCODE_GO_API_KEY`。不再新增模型页独立区域。已知支持图片的 Kimi/MiMo 模型写入 `input: [text, image]`；其余模型保持纯文本。
- 主要文件：`plugins/dsh-mathmodel/src/opencode-rt.js`、`src/host.js`、`src/typert-shared.js`、`src/client-bundle.cjs`、构建清单与对应测试；OpenSpec 记录已归档至 `openspec/changes/archive/2026-08-16-add-opencode-rt/`。
- 官方冲突面：依赖 DSH Settings Service 的 `llm-pi-ai` 分节、Typert Remote 与模型页标题挂载点；OpenCode 的公开 `/models` 仅提供模型 ID，因此 `/messages`、`/responses` 和未知能力模型不得伪装成 Chat Completions。
- 安全边界：不修改 DSH 全局安装包或官方 `node_modules`；API Key 只经受管凭据存储，错误不回显 Key。`opencode-rt` 不提供生图接口。
- 验证：`npm run check`、插件全量测试、`dsh --profile web --dump-config` 通过；官方实时清单为 26 个模型，其中 11 个已按协议安全接入，15 个保留待支持；浏览器验证下拉菜单出现 `OpenCode RT`，且不显示独立模型设置区。
- 回滚：在“模型”页面删除 `OpenCode RT` 提供方，并在 `cordis.patch.yml` 暂时禁用 `mathmodel` 后重启 Web；不删除 `opencode-go`，不修改官方安装目录。

### GOAL-20260816-21：已保存 API Key 的模型列表复用

- 时间：**2026-08-16 16:10:03 +08:00**
- 原因：自定义供应商首次输入 API Key 时可拉取模型，但保存后编辑同一供应商再次拉取会走已保存凭据分支并报 401；聊天模型仍可正常使用，问题不在 Base URL、模型名或 Key 本身。
- 修改：新增外置插件的 `StoredKeyModelDiscoveryService`。模型页编辑已配置自定义供应商时，点击“获取可用模型”只向插件 Remote 传递供应商 ID；服务端按该供应商当前 `llm-pi-ai` 配置解析受管 Key，再请求固定的 `<baseURL>/models`。返回模型先供用户勾选，选中项只加入当前原生草稿，仍需点击官方“保存”才会写入配置。`opencode-rt` 则继续走受控同步，只写入已验证的兼容模型，不通过通用列表加入未知协议模型。
- 主要文件：`plugins/dsh-mathmodel/src/model-discovery.js`、`src/host.js`、`src/typert-shared.js`、`src/client-bundle.cjs`、`src/index.js`、构建清单和 `test/model-discovery.test.mjs`；OpenSpec 记录已归档至 `openspec/changes/archive/2026-08-16-fix-stored-key-model-discovery/`。
- 官方冲突面：依赖 DSH `0.1.0-rc.6` 的模型页“获取可用模型”按钮、模型目录输入框和 Typert Remote；找不到这些稳定控件时插件不拦截原生按钮。官方升级后需重建并重新做浏览器验收。
- 安全边界：不修改 DSH 全局安装包、`settings.yaml` 或任何凭据文件；浏览器不接收已保存 Key，Remote 不接受任意 URL，错误会脱敏。`/models` 返回 401/403 时仅说明模型列表端点被拒绝，不再断言聊天模型或 API Key 不可用；用户仍可手动添加模型。
- 验证：`npm run check`、插件全量测试、OpenSpec 严格校验与 `dsh --profile web --dump-config` 通过。浏览器实测模型选择框位于官方“设置”弹窗之上，且“取消”可点击关闭；`opencode-rt` 的刷新不再显示通用选择框，因此不会误加入未知协议模型；未点击“加入当前草稿”或“保存”，现有配置未被本次验收改动。
- 回滚：移除本记录所列的模型发现服务、Remote、客户端适配和测试后重新构建插件；无需改动任何供应商、模型或 Key。

### GOAL-20260816-22：生图多连接与当前模型切换实施计划

- 时间：**2026-08-16 16:32:29 +08:00**
- 原因：当前生图配置固定为百炼、OpenAI、Gemini、单个自定义项四个槽位，无法同时保存多个自定义模型/账号，也没有明确的当前生图模型切换入口；固定顺序自动兜底还可能造成不透明的多供应商付费尝试。
- 修改：新增 `.dsh/计划文档/生图文档.md`，锁定“多条独立生图连接 + 标题右侧当前连接选择器”的产品、数据、迁移、凭据、协议验证、火山/Sub2API/CLIProxyAPI 模板、测试、回滚和官方升级策略。本记录仅创建计划与维护说明，尚未修改运行代码、模型、凭据或 DSH 配置。
- 主要文件：`.dsh/计划文档/生图文档.md`、`README.md`。
- 官方冲突面：未来实现将依赖 DSH Settings Service、Credentials、Typert Remote、模型设置页标题挂载点与设置弹窗 portal；必须沿用外置插件，不能编辑官方包。
- 安全边界：未知模型不得因 `/models` 或名称被标为可生图；真实验证需用户主动确认潜在费用；Key 仅经受管凭据服务保存，删除连接默认不删 Key；默认生图禁止自动多供应商兜底。
- 验证：已完成现有实现、`MetaMath-Agent-demo` 参考链路和供应商官方资料的方案审查，并完成内部严格拷问；功能代码、真实 API、浏览器交互和构建测试均**尚未执行**。
- 回滚：删除或恢复本次计划文档与本条台账不会影响任何运行行为；若后续实施则按计划第 10 节进行功能回滚。

### GOAL-20260816-23：手动图片转写与插件加载恢复

- 时间：**2026-08-16 17:14:09 +08:00**
- 原因：纯文本模型收到图片会被 Harness 正确拒绝；用户要求通过 `claude-vision-skill` 识图，但明确禁止自动触发。同时，构建后的浏览器插件缺少 `createImageProviderActions`，且生图连接 Remote 使用了与 DSH 客户端保留服务冲突的 `remove` 方法，导致页面显示“Failed to load plugins”。
- 修改：在输入框发送按钮左侧增加仅当存在图片时可见的“识图转写 N”手动按钮。只有用户点击它，才使用受管 `DASHSCOPE_API_KEY` 调用既有主备视觉模型；成功后把带 `图片视觉转写（claude-vision-skill）` 标记的描述写入可编辑草稿、移除未发送原图，用户仍须自行发送。普通上传、普通发送、模型切换及官方能力拒绝均不会触发识图。补回 v1 生图设置兼容动作，并将内部生图连接 Remote 的冲突方法改名为 `deleteConnection`。
- 主要文件：`plugins/dsh-mathmodel/src/vision.js`、`src/host.js`、`src/typert-shared.js`、`src/client-bundle.cjs`、`src/index.js`、`types/index.d.ts`、相应测试；规格位于 `openspec/changes/universal-image-vision-fallback/`。
- 官方冲突面：依赖 DSH `0.1.0-rc.6` 的 `conversation.input.right` 插槽、草稿图片接口、Typert Remote 服务命名及受管凭据服务。未修改官方包、`node_modules`、模型能力声明或任何已保存 Key。
- 安全边界：不把文本模型伪装为原生多模态；不自动识图、不自动发送；视觉 Remote 不接收用户全文或 API Key，只接收受限图片数据；失败时不改写草稿、不移除原图，图片仅支持 PNG/JPEG/WebP/GIF，最多 4 张、单张 20 MiB、总计 32 MiB。
- 验证：`npm run build`、`npm run check` 通过；相关 21 项单元测试通过；OpenSpec 严格校验通过。使用本地浏览器打开 `http://127.0.0.1:3080` 已确认插件正常加载、白屏错误消失、正常会话与输入框可用。
- 回滚：在 `cordis.patch.yml` 暂时禁用 `dsh-mathmodel` 后重启 Web，可立即恢复官方 Harness；不要修改官方安装包。若只回退本功能，移除手动视觉 Remote、输入区按钮及相关测试后重新构建。

### GOAL-20260816-24：生图多连接、全模式可用与旧 Host 兼容

- 时间：**2026-08-16 17:36:00 +08:00**
- 修改：生图配置改为独立连接列表，支持百炼、OpenAI、Gemini、火山 Ark、Sub2API、CLIProxyAPI 和通用 OpenAI 兼容模板；每条连接隔离受管 Key，只有完成真实测试的连接可设为当前。`image_generate` 默认使用当前连接，可选 `connectionId` 精确指定，旧 `provider` 只保留兼容映射，取消自动多供应商兜底。`mathmodel-tools` 由 Web Profile 全局且仅挂载一次，两个本地预设移除重复项，因此任意 Agent 模式都能调用生图工具。
- 兼容：运行中的旧 Host 没有新 Remote 时，客户端以只读历史连接摘要回退并提示重启，不再显示红色 404 或导致 Skills/插件消失；重启后自动使用完整多连接 Remote。兼容探测本身不请求不存在的新端点。
- 主要文件：`plugins/dsh-mathmodel/src/security/image-connections.js`、`src/security/image-credentials.js`、`src/image/{connections,verify,service,adapters}.js`、`src/host.js`、`src/typert-shared.js`、`src/client-bundle.cjs`、`src/tool-contracts.js`、`src/tools.js`、`.dsh/profiles/web/cordis.patch.yml`、本地 Preset、`.dsh/skills/imagegen/` 与专项测试。
- 安全边界：浏览器不接收 Key、完整 Prompt、下载 URL 或验证响应；真实测试需要显式确认可能产生费用；删除默认保留 Key；验证失败、未验证或缺 Key 时拒绝设为当前和生成；无自动切换收费供应商。
- 验证：`npm run check`、`npm test`（103/103，含 OpenAI Images、Sub2API 轮询回退/取消和 Chat 图片解析专项测试）、`npm run build`、`openspec validate multi-image-connections --strict`、`dsh --profile web --dump-config` 均通过；旧 Host 下模型页不再显示 404、Skills 前端正常且控制台 0 error。全新 3083 Host 的标准模式实测“生图模型”可见、`/imagegen` 仅作为手动 Skill 出现在候选中、控制台错误 0；真实收费供应商测试仍需在用户已授权的连接上手动执行。

### GOAL-20260816-25：生图附件类型不匹配的魔数嗅探修复

- 时间：**2026-08-16 18:41:30 +08:00**
- 原因：`/imagegen` 真实调用报 `Declared image type does not match its bytes`。OpenAI Images 协议的 `b64_json` 不携带 MIME 声明，适配器一律默认 `image/png`，解码与落盘从不校验真实字节；供应商实际返回 JPEG 时，JPEG 字节被存成 `.png`，官方附件服务 `@deepseek-ai/dsh-attachment-local` 嗅探字节后发现声明类型与实际不符而拒绝入库。付费调用已成功返回图片字节，仅展示环节失败。
- 修改：`src/image/assets.js` 新增 `sniffImageMime(bytes)` 魔数嗅探（PNG/JPEG/WebP/GIF）；`decodeImageAsset` 与 `downloadImage` 改为以嗅探结果为唯一事实源，纠正供应商与响应头可能不实的类型声明；无法识别的字节以新错误码 `invalid_image_bytes` 失败关闭，不再落盘。文件扩展名与附件 `mediaType` 随真实 MIME 自动正确。同步把两处使用假图片字节的测试 fixture 更新为真实 1x1 PNG，并新增"JPEG 字节纠正为 `.jpg`"与"非图片字节失败关闭且不落盘"两个回归测试。
- 主要文件：`plugins/dsh-mathmodel/src/image/assets.js`、`plugins/dsh-mathmodel/test/image-generation.test.mjs`、`plugins/dsh-mathmodel/test/connection-verify.test.mjs`、`README.md`。
- 官方冲突面：无官方源码修改；仅对齐官方附件服务的字节嗅探行为。若官方未来放宽或收紧 `saveImage` 支持的图片类型集合，需同步调整 `sniffImageMime`。
- 安全边界：不放宽任何付费门禁、凭据或路径约束；非图片字节、伪装类型的响应现在会更早被拒绝，不会写入工作区。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **106/106**（原 104 + 新增 2，原有测试零破坏）；3080 服务已用新构建重启（HTTP 200）。历史残留的 `image-1786789515299-1.png`（300 KB，魔数 `FF D8 FF E0` 实为 JPEG）已重命名为 `.jpg`，字节未动。真实付费生图复测需用户在 `/imagegen` 中再次授权发起。
- 回滚：恢复 `assets.js` 中 `decodeImageAsset`/`downloadImage` 的旧实现并移除 `sniffImageMime`，恢复两个测试文件的 fixture，重新 `npm run build` 并重启 Web；无官方文件或配置需要回滚。

### GOAL-20260816-26：识图转写改为附图给模型（模型自主经 vision_analyze 看原图）

- 时间：**2026-08-16 19:12:00 +08:00**
- 原因：用户反馈不想要"识图转写"（视觉模型读图生成固定文字描述插入草稿，存在抄录误差且需人工检查文本）。期望纯文本模型也能"上传→发送→模型分析"，且模型看的是原图而非二手转述。多模态模型直发图片为官方原生能力，保持零改动。
- 修改：`ManualVisionService.transcribe`（调视觉供应商转写）整体替换为 `stageDraftImages`——纯本地把草稿原图落盘到会话工作区 `uploads/img-<时间戳>-<序号>.<ext>`（`wx` 独占创建，零 API 调用、零费用），返回相对路径；Remote 由 `mathmodelManualVision/transcribe` 改为 `stage(images, workspace)`；客户端按钮由"识图转写 N"改为"附图分析 N"，成功后草稿移除原图并插入 `[已附图片（claude-vision-skill）——请用 vision_analyze 工具查看原图]` 标记块（每行 `图片 N（原名）：uploads/...`），由用户手动发送；会话 cwd 经官方同款编程访问器 `sessions.list.getSnapshot().byId[sessionId]?.cwd` 获取（官方 client.js:9732 同款），无工作区时失败关闭。模型侧 `vision_analyze` 工具原生支持工作区相对路径（GOAL-24 起全局挂载），零改动。
- 主要文件：`plugins/dsh-mathmodel/src/vision.js`、`plugins/dsh-mathmodel/src/typert-shared.js`、`plugins/dsh-mathmodel/src/host.js`、`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/types/index.d.ts`、`plugins/dsh-mathmodel/test/vision.test.mjs`、`plugins/dsh-mathmodel/test/manual-vision-client.test.mjs`、`README.md`。
- 官方冲突面：无官方源码修改。复测点：`sessions.list.getSnapshot().byId[*].cwd` 编程访问器与 `conversation.draftImages/releaseDraftImages` 草稿接口在新版官方的行为。
- 安全边界：附图按钮是唯一入口且仅手动触发；不自动发送、不自动识图；落盘前校验规范 Base64、MIME 白名单（PNG/JPEG/WebP/GIF）、4 张/单张 20 MB/总量 32 MB 上限与工作区存在性；文件名服务端生成（客户端不可控子路径），`wx` 标志防覆盖；视觉调用仅在用户发送后由模型按需发起（需 DASHSCOPE_API_KEY，失败返回清晰错误码）。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **107/107**（手动视觉测试重写为真实临时目录落盘验证：字节一致性、相对路径、非规范 Base64/工作区不存在/无工作区三类失败关闭；客户端测试 3→4 个含无工作区与失败不改草稿用例）；3080 服务已用新构建重启（HTTP 200，进程 32964）。浏览器端真实点击按钮复测待用户在 Web UI 中发起。
- 回滚：恢复 `vision.js` 的 `transcribe` 实现、`typert-shared.js`/`host.js` 的 `transcribe` Remote、`client-bundle.cjs` 的按钮与动作（见 git 历史 GOAL-23 版本），重新 `npm run build` 并重启 Web；无官方文件或配置需要回滚。

### GOAL-20260816-27：百炼 Key 已配置后隐藏 claude-vision-skill 配置卡片

- 时间：**2026-08-16 19:53:00 +08:00**
- 原因：用户完成 claude-vision-skill（DASHSCOPE_API_KEY）配置后，配置卡片不再有日常用途，仍出现在 `/` 技能候选与技能说明面板中造成干扰；希望配置完成后不再跳出。
- 修改：仅 `client-bundle.cjs` 三处。`createSkillSource` 新增可选 `hideSkill(name)` 参数，`candidates()` 在官方目录过滤后再按其异步结果剔除命中技能（未传参数时行为与原先完全一致）；`apply()` 内新增 `visionConfigured()` 闭包——经既有 `mathmodelCredentials/describe` Remote 查询 `DASHSCOPE_API_KEY.configured`，30 秒 TTL 缓存，查询失败时返回 false（不过滤、保持可见，失败关闭）；`loadSkillHelp` 包装为配置后过滤 `claude-vision-skill` 条目（返回新对象，不改 freeze 的原数组）；`/` 候选经 `hideSkill` 仅对 `claude-vision-skill` 生效。凭据 `set`/`unset` 成功与 `connection/reset` 时立即清缓存，配置状态变化无 30 秒窗口。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/test/client-flow.test.mjs`、`README.md`。
- 官方冲突面：无官方源码修改。复测点：`mathmodelCredentials/describe` Remote 与官方 `skills.list` 目录行为。
- 安全边界：只隐藏入口不删除能力——Key 未配置或查询失败时卡片照常显示可用；`vision_analyze` 工具与附图分析按钮（GOAL-26）不受影响；清除 Key（unset）后卡片立即重新可见。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **108/108**（新增"hideSkill 命中的技能不出现在候选，未命中的保持不变"回归测试）；3080 服务已用新构建重启（HTTP 200，PID 8956，启动 19:51:41 晚于构建 19:49:37，二次确认存活）。浏览器端 `/` 候选与说明面板复测待用户刷新页面确认。
- 回滚：`createSkillSource` 移除 `hideSkill` 参数与过滤块、`apply()` 移除 `visionConfigured` 闭包并还原 `loadSkillHelp`/`credentialActions` 为直通调用、调用点移除 `hideSkill`，重新 `npm run build` 并重启 Web。

### GOAL-20260816-28：回滚 GOAL-27，claude-vision-skill 完全复原可见

- 时间：**2026-08-16 20:08:00 +08:00**
- 原因：GOAL-27 把"配置完成后不再跳出卡片"实现为按 `DASHSCOPE_API_KEY.configured` 永久过滤，导致用户（Key 早已配置）在 `/` 候选与技能说明面板中再也找不到 claude-vision-skill，超出用户本意。用户澄清：技能必须随时可见可用，不要永久隐藏。
- 修改：完全回滚 GOAL-27 全部四处改动——`createSkillSource` 还原为无 `hideSkill` 参数；`apply()` 移除 `visionConfigured` 闭包与 `loadSkillHelp` 过滤包装、`credentialActions` set/unset 还原直通、`connection/reset` 移除缓存清除；删除对应回归测试。代码回到 GOAL-26 后的基线状态。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/test/client-flow.test.mjs`、`README.md`。
- 官方冲突面：无。
- 安全边界：无行为变化；技能入口、卡片、`vision_analyze`、附图分析按钮全部恢复 GOAL-26 状态。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **107/107**（与 GOAL-26 基线一致）；3080 服务已重启（HTTP 200，PID 26944，启动 20:07:12 晚于构建 20:07:02，二次确认存活）。浏览器端 `/claude-vision-skill` 候选复现待用户刷新确认。
- 回滚：本条即为回滚记录；如需再次启用隐藏行为，参考 GOAL-27 的实现重新应用。

### GOAL-20260816-29：附图路径改为绝对路径并优化按钮文案

- 时间：**2026-08-16 20:12:00 +08:00**
- 原因：用户确认附图草稿标记中的相对路径改为绝对路径（在草稿中可直接看到文件完整位置）；按钮文案"附图分析1"数字直接拼接易误读，需带单位的清晰格式。
- 修改：`vision.js` 的 `stageDraftImages` 落盘返回 `path` 由相对 `uploads/...` 改为绝对路径（`join(root, 'uploads', filename)`）；`client-bundle.cjs` 按钮文案改为"附图分析（N 张）"/忙碌态"附图中 N 张…"。`vision_analyze` 工具的 `imageSource` 原生支持工作区内绝对路径（`resolve` + `inside` 边界校验），模型侧零改动。
- 主要文件：`plugins/dsh-mathmodel/src/vision.js`、`plugins/dsh-mathmodel/src/client-bundle.cjs`、`plugins/dsh-mathmodel/test/vision.test.mjs`、`plugins/dsh-mathmodel/test/manual-vision-client.test.mjs`、`README.md`。
- 官方冲突面：无。
- 安全边界：绝对路径仍受 `inside(workspace)` 校验约束，工作区外路径依旧拒绝；不放宽任何既有校验。绝对路径会随对话进入会话历史，用户已知晓并确认。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **107/107**（vision 测试断言绝对路径与盘符正则；client 测试 mock 同步绝对路径）；3080 服务已重启（HTTP 200，PID 13240，启动 20:11:08 晚于构建）。浏览器端按钮文案与实际附图复测待用户刷新确认。
- 回滚：`stageDraftImages` 的 `path` 恢复为 `uploads/${filename}`、按钮文案恢复 `附图分析 ${imageIds.length}`，恢复两个测试文件的断言，重新 `npm run build` 并重启 Web。

### GOAL-20260816-30：附图路径回滚为相对路径（保留按钮文案优化）

- 时间：**2026-08-16 20:16:00 +08:00**
- 原因：对比评估后确认相对路径更优——对话历史不污染、工作区移动不失效、不泄露本机目录结构；用户决定改回相对路径。GOAL-29 的按钮文案优化（"附图分析（N 张）"）保留。
- 修改：`vision.js` 的 `stageDraftImages` 返回 `path` 由绝对路径回滚为相对 `uploads/${filename}`；两个测试文件断言同步回滚。
- 主要文件：`plugins/dsh-mathmodel/src/vision.js`、`plugins/dsh-mathmodel/test/vision.test.mjs`、`plugins/dsh-mathmodel/test/manual-vision-client.test.mjs`、`README.md`。
- 官方冲突面：无。
- 安全边界：与 GOAL-26 一致，无变化。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **107/107**；3080 服务已重启（HTTP 200，PID 24236）。
- 回滚：如需再改绝对路径，参考 GOAL-29 实现。

### GOAL-20260817-32：桌面快捷方式启动提速（探活毫秒级 + 直拉 node）

- 时间：**2026-08-17（GOAL-31 之前）**
- 原因：双击桌面快捷方式启动慢。实测 `Test-NetConnection 127.0.0.1 -Port 3080` 单次 13.07 秒（枚举网卡 + 加载 NetTCPIP 模块），等效裸 `TcpClient` 仅 7ms；冷启动时嵌套 powershell 再付约 1 秒。
- 修改：`启动-MetaMath-Harness.ps1` 与 `.release-staging/metamath-harness/install.ps1` 两处探活改为 `TcpClient.ConnectAsync + 500ms 超时`；服务启动优先直拉 `node <dsh>/lib/bin.js web --port`（省去嵌套 PowerShell，不再残留 `-NoExit` 窗口），找不到 node/dsh 时回退原 powershell 方式；两文件补 UTF-8 BOM（Edit 重写后变无 BOM，PowerShell 5.1 按 ANSI 读中文乱码致脚本无法运行）。
- 主要文件：`启动-MetaMath-Harness.ps1`、`.release-staging/metamath-harness/install.ps1`。
- 官方冲突面：无（仅本地启动脚本）。
- 安全边界：探活语义不变（仅测端口连通）；直拉 node 路径与官方 `dsh web` 等价；回退链保证无 node 环境不破坏原行为。
- 验证：两文件引擎级语法解析 0 错误；探活实测与裸连接判定一致；复用路径全程 **2.01 秒**（修复前 ~14 秒）；冷启动 **3.65 秒**（本机热缓存）；服务独立常驻监听 3080。
- 回滚：恢复 `Test-NetConnection` 与嵌套 powershell 启动段即可。

### GOAL-20260817-33：中央主标题改为“大道至简”艺术字并移除“预览版”徽章

- 时间：**2026-08-17（GOAL-31 之后）**
- 原因：用户要求中央主视觉文案由官方“探索未至之境”改为“大道至简”艺术字，并去掉“预览版”徽章，与 MetaMath 品牌统一。
- 修改：`client-bundle.cjs` 新增 `installMetaMathHeroTitle()`：命中官方 `span[class*="_headlineText"]` 后清空文案并注入 `img.dsh-mm-hero-title-img`（用户提供的“大道至简”金属艺术字，经洪水填充去背景、小碎片去噪、字内封闭黑块与深灰锯齿条透明化、裁边后内嵌为透明底 PNG 资产 `src/assets/metamath-hero-title.png`，高 34px）；headline 行 `gridTemplateColumns` 由 `34px auto auto` 改为 `34px auto`（徽章列移除后保持居中）；`span[class*="_previewBadge"]` 隐藏；MutationObserver 持久化，与 GOAL-19/31 同款运行时覆盖思路；`build.mjs` 新增 `__METAMATH_HERO_TITLE__` 占位符；新增 1 项源码回归测试。
- 主要文件：`plugins/dsh-mathmodel/src/client-bundle.cjs`、`test/client-panel.test.mjs`、`README.md`。
- 官方冲突面：依赖 `HeroShell.module.css` 的 `_headlineText` / `_previewBadge` 语义类名与 headline 三列 grid 结构（`dsh-client-ui-conversation` client.js:6585-6612、6727-6745）；官方改版 hero 结构后需复核。未修改官方包或任何后端/Host 代码。
- 安全边界：纯客户端运行时覆盖，无网络请求、凭据或遥测；卸载插件即恢复官方文案与徽章。
- 验证：`npm run build`（30 个文件）、`npm run check`、`npm test` **109/109**（新增 1 项）；3080 服务已用新构建重启（HTTP 200）。
- 回滚：删除 `installMetaMathHeroTitle` 及其 MutationObserver、`.dsh-mm-hero-title` CSS 与对应测试，重新 `npm run build` 并重启 Web；GOAL-19/31 不受影响。

### GOAL-20260817-34：适配 dsh-client-ui-skins 全局皮肤插件（含 FX 微调增强）

- 时间：**2026-08-17（GOAL-33 之后）**
- 原因：用户要求把第三方皮肤插件 `caoyiwei850/dsh-client-ui-skins`（v0.1.9）适配进本项目：上传 PNG/JPG/WebP 作全局背景、自动取主色适配整套配色、Blur/Dim/面板不透明度可调、重启保留、一键恢复默认；不重写 DSH、不覆盖现有 `cordis.patch.yml`。
- 兼容性核查：插件 peerDeps `^0.1.0-rc.6` 与本项目 dsh `0.1.0-rc.6` 完全匹配；client inject 所需 6 包（runtime/locale/ui-settings/ui-slots/ui-theme/connection）与 Host 侧 `dsh-settings`/`schemastery` 均已随 dsh 本体存在于全局 node_modules，**无需 compatibility adapter、未降级任何组件**；现有插件无 skin/theme/wallpaper 功能，零冲突。
- 修改：① 新增 `plugins/dsh-client-ui-skins/`（自上游 v0.1.9 复制 `lib/`、`package.json`、`cordis.patch.yml`、LICENSE、README）；② 增强 `lib/client.js`：新增 FX 层——`loadFx/saveFx`（localStorage `dsh-skins.custom.fx`，默认 `{blur:0, dim:-1, panelAlpha:-1}`，-1=自动跟随图片）、`applyBackground` 增加 `--dsh-skin-bg-blur`/`--dsh-skin-bg-blur-scale`（背景模糊 + 边缘放大补偿）、`applySkinState` 增加 `--dsw-alias-bg-base` 面板不透明度覆写（毛玻璃浓度）、SkinsRow 新增"效果微调"三滑杆（背景模糊 0-24px／遮罩浓度 0-90%／面板不透明度 5-100%，仅自定义皮肤激活时显示）、i18n 中英文与 `.dsh-skins-fx-*` 样式；③ `.dsh/profiles/web/package.json` 增 `dsh-client-ui-skins: file:../../../plugins/dsh-client-ui-skins`；④ `cordis.patch.yml` **追加**（未动既有条目）`ui-skins` insert 条目。
- 主要文件：`plugins/dsh-client-ui-skins/lib/client.js`、`.dsh/profiles/web/package.json`、`.dsh/profiles/web/cordis.patch.yml`。
- 官方冲突面：零侵入——走官方 `theme.register` 皮肤注册、`settings.general.item` 设置插槽与 `--dsw-alias-*` 官方 token 体系；所有自定义 CSS/变量都在 `dsh-skins-*` / `dsh-skin-*` 独立命名空间；图片与配置仅存浏览器 localStorage，不经 Host settings 通道，不上传任何地方。
- 验证：`node --check` 双文件 0 语法错误；`pnpm install --no-frozen-lockfile` 干净装链；服务重启后 `/plugins/dsh-client-ui-skins/client.js` HTTP 200（63KB 增强版含全部 FX 代码）、`__DSH_BOOT__` entries 已注册；浏览器 E2E **10/10 通过**：上传图片→全局背景生效（Sidebar/聊天/输入/设置全覆盖）、主色自动适配、三滑杆实时联动（blur 8px、panelAlpha 0.6 实测写入 CSS 变量）、localStorage 持久化、刷新自动恢复、切"默认"一键还原（`dsh-skins.active=system`）、全程无插件相关 console 报错。
- 回滚：`cordis.patch.yml` 删除 `ui-skins` 条目 + `package.json` 删该依赖 + `pnpm install`，或直接删 `plugins/dsh-client-ui-skins/` 目录三步即可完全卸载；界面残留时清 localStorage `dsh-skins.*` 四键即回官方原生主题。

### GOAL-20260817-35：内置 10 张壁纸进皮肤插件 + 移除中央紫鲸鱼、标题与对话框水平居中

- 时间：**2026-08-17（GOAL-34 之后）**
- 原因：用户要求把 `.dsh/皮肤/` 的 10 张 PNG 内置进皮肤设置“图一”位置（dsh 无插件静态资源路由，故 base64 内嵌）；中央紫色鲸鱼图标不要；“大道至简”与对话框水平居中对齐。
- 修改：① `plugins/dsh-client-ui-skins/lib/client.js`：新增 `BUNDLED_WALLPAPERS`（10 张图压 JPEG q78、长边≤1920，base64 共 1.09MB）+ `bundledById/isBundledSkin`；seeds 由 Python 复刻官方 `processImage` 采样算法离线预计算（64px 网格、饱和色桶取主色、亮度定 veil），与运行时算法一致；接入 7 处：`resolveSkinTokens`（`deriveTokens(seeds, true)` 壁纸走照片分支）、`isOurSkin`、`applySkinState`（背景层 + accent）、`applySkin`、恢复分支（壁纸未注册 theme 服务，直接 adopt id + 延迟重绘）、SkinsRow（缩略图=照片本身的 10 张卡片 + FX 滑杆对壁纸同样可用）；② `plugins/dsh-mathmodel/src/client-bundle.cjs`：删除 `installMetaMathHeroMark` 与 `metaMathHeroMark` 变量、`.dsh-mm-hero-mark` CSS，改为 `hideMetaMathHeroFish()`（hitbox 与官方 svg 均 `display:none`，MutationObserver 持久）；标题行 `gridTemplateColumns='auto'` + `justifyContent='center'` 整行居中；③ `scripts/build.mjs` 移除 `__METAMATH_HERO_MARK__` 占位符；④ 测试同步更新。
- 主要文件：`plugins/dsh-client-ui-skins/lib/client.js`、`plugins/dsh-mathmodel/src/client-bundle.cjs`、`scripts/build.mjs`、`test/client-panel.test.mjs`。
- 验证：`node --check` 0 错误；构建 30 文件、测试 109/109；浏览器 E2E：皮肤区出现“壁纸 01–10”10 卡片、点“壁纸 03/05”→ `data-dsh-skin-bg="image"` + `dsh-skins.active=skin-wall-0X`、效果微调滑杆可用、**刷新后壁纸自动恢复**、点“默认”回 `system`；官方鲸鱼 `display:none` 且无 hero-mark img；标题中心 x=439 vs 对话框中心 x=434（差 5px，视口半宽 984 为侧栏展开态，主内容区居中正确）；console 无插件相关报错。
- 回滚：皮肤区点“默认”即恢复；代码层回滚为移除 `BUNDLED_WALLPAPERS` 片段与 hero 隐藏函数（git 可回溯）。

### GOAL-20260817-31：中央主视觉鲸鱼图标替换为 MetaMath 四象限标记

- 时间：**2026-08-17 10:16:00 +08:00**
- 原因：Web 新会话主视觉（"探索未至之境"标题左侧）仍显示官方黑色鲸鱼图标，与左上角 MetaMath 品牌不统一；用户要求替换为 `MetaMath-Harness.ico` 的四象限鲸鱼标记并裁剪边框空白。
- 修改：从 ICO 提取 256px 帧并按 alpha 边界框裁剪透明边（256×256 内容占满，实际裁出紧凑图），存为新资产 `src/assets/metamath-hero-mark.png`；`scripts/build.mjs` 新增 `__METAMATH_HERO_MARK__` 占位符内嵌；`client-bundle.cjs` 新增 `installMetaMathHeroMark()`：在官方 `span[class*="_fishHitbox"]` 内隐藏官方 `FishLogo` SVG 并注入 34px `img.dsh-mm-hero-mark`（data URL，MutationObserver 持久化，与 GOAL-19 左上角品牌同款运行时覆盖思路）；新增对应 CSS 与 1 项源码回归测试。
- 主要文件：`plugins/dsh-mathmodel/src/assets/metamath-hero-mark.png`、`src/client-bundle.cjs`、`scripts/build.mjs`、`test/client-panel.test.mjs`、`README.md`。
- 官方冲突面：依赖官方 `HeroShell.module.css` 的 `_fishHitbox` 语义类名与内部 `FishLogo` SVG 结构（`dsh-client-ui-conversation` client.js:6721-6747）；官方改版 hero 结构后需复核该挂载点。未修改官方包、`node_modules` 或任何后端/Host 代码。
- 安全边界：纯客户端运行时覆盖，图标为本地资产内嵌，无网络请求、凭据或遥测；卸载插件即恢复官方图标。
- 验证：`npm run build`（30 个文件，lib 占位符残留 0）、`npm run check`、`npm test` **108/108**（新增 1 项中央图标回归测试）；3080 服务已用新构建重启（HTTP 200）。真实浏览器确认 hero 状态、左上角 MetaMath HARNESS 字标完好、控制台 error 0 并已截图；DOM 级 evaluate 受浏览器工具限制未执行，以源码断言与截图佐证。
- 回滚：删除 `installMetaMathHeroMark` 及其 MutationObserver、`.dsh-mm-hero-mark` CSS、`__METAMATH_HERO_MARK__` 占位与资产文件，重新 `npm run build` 并重启 Web；左上角品牌（GOAL-19）不受影响。

### GOAL-20260817-36：同步 drawio 十类模板与嵌套校验优化

- 时间：**2026-08-17 18:20:00 +08:00**
- 原因：上游 `F:\github装饰\math-paper-cn` 与 `math-paper-huashu` 的 Draw.io 模板库从六类扩到十类（新增双栏双层联动、三段环抱式、侧标步骤栏、纵向步骤带横幅，借鉴用户本人原创模板 `draw.io模板/2-5` 的版式语法后原创重绘），并新增 container/zone/action/caption 四种角色与“完全嵌套合法”的重叠校验规则；本地两套论文 Skill 需要同步该优化，同时保留 DSH 专属适配。
- 修改：`template_library.json` 升级 version 2 并追加 4 个模板；`drawio_pipeline.py` 追加 4 角色、4 条选路规则（panels/side_head/output_banner/focus_stage，旧 brief 选路逐一不变）与嵌套合法化重叠校验；`references/drawing-pipeline.md` 第 7 条由六类改为十类；`assets/drawio/UPSTREAM.md` 追加用户自绘模板来源行。DSH 版 `drawio_pipeline.py` 采用补丁方式合并，保留 `DSH_RUNTIME_ROOT`/`DSH_PORTABLE_STRICT` 严格便携模式与 `wait_for_stable_output` Electron 异步写盘等待，未被上游版本覆盖。
- 主要文件：`.dsh/skills/math-paper-cn/` 与 `.dsh/skills/math-paper-huashu/` 内的 `assets/drawio/template_library.json`、`assets/drawio/UPSTREAM.md`、`references/drawing-pipeline.md`、`scripts/drawing/drawio_pipeline.py`；其余文件零改动。
- 官方冲突面：无官方源码、插件 API 或 UI 修改；仅改变两套本地论文 Skill 的 Draw.io 模板库与静态校验规则。
- 安全边界：未修改 `F:\github装饰` 上游仓库之外的任何系统配置；未触碰凭据、论文工作区或运行中的服务；新增模板坐标与文案均为原创中文重绘，不复制第三方图稿内容。
- 验证：两套 Skill 各 **10/10** 模板 build+validate 通过（含 6 个旧模板回归）；选路回归 7 用例全部符合预期（旧 brief 结果不变、4 个新键命中新模板、混合优先级正确）；两副本 `fc` 逐字节一致；`wait_for_stable_output`/`DSH_RUNTIME_ROOT` 适配代码保留（命中 4 处）。上游两仓库同样 10/10 通过并与本地补丁内容一致。
- 回滚：将 `template_library.json`、`drawing-pipeline.md`、`UPSTREAM.md` 恢复为同步前版本，并按备份反向应用 `drawio_pipeline.py` 的 4 处补丁（或整体恢复同步前 DSH 版本）；不涉及官方 Harness 文件。

### GOAL-20260817-37：华为杯专用 Skill（math-paper-huawei）落地并适配 DSH

- 时间：**2026-08-17（GOAL-36 之后）**
- 原因：用户要求把 `.dsh/skills/math-paper-huawei/` 改造为华为杯（中国研究生数学建模竞赛）专用 Skill：内置 GMCMthesis 模板小幅更新为 2026 年版，登记 `华为杯优秀论文_2023_2024/`（2023 年 69 篇 + 2024 年 1 篇，只读参考、只学不抄），并像 math-paper-cn/huashu 一样接入 DSH 小卡、手动目录与阶段门禁；严格保持其他内容不变。
- 修改：① 模板 2026 化（最小改动）：`laTeX-模板-GMCMthesis/` 的 `example.tex`、`example-color.tex` 参赛队号 `20250900001→20260900001`，`gmcmthesis.cls` 版本日期 `2026/09/20`，模板 README 标题与更新记录；② 技能身份：`SKILL.md` 由 math-paper-cn 副本改造为华为杯定位（含优秀论文参考规则），新建 `mathmodel-card.yml`（华为杯论文一键运行小卡，`reference_excellent_papers` 开关）、`agents/openai.yaml`、技能 `README.md`；③ 内置模板基座：新建 `assets/templates/main.tex`（gmcmthesis 结构 + `body:start/end`、`abstract:end`、`appendix:start` 等门禁标签）；④ 门禁适配 gmcmthesis 双分支：`scripts/checks/` 的 `common.py`、`check_template_adherence.py`（必需标记改为 `\documentclass[bwprint]{gmcmthesis}`、`\baominghao{`、`\begin{abstract}`、`\begin{appendices}` 等）、`check_abstract_one_page.py`、`check_paper_emphasis.py`（改查 `\keywords{...}`）、`check_paper_section_whitelist.py`（华为杯固定章节"问题重述/模型假设与符号说明/模型总结与评价"+"问题X模型建立与求解"）、`check_abstract_no_formula.py`（华为杯跳过国赛摘要禁公式硬门）、`run_stage_gate.py`/`run_all_checks.py` 路径指向 math-paper-huawei；`scripts/plotting/python_flowchart.py` 路径同步；⑤ 插件注册：`src/cards/registry.js`、`lib/cards/registry.js`、`lib/skills/catalog.js` 增加华为杯 HELP 小卡行，4 个测试文件加入名单，`test/card-snapshots.json` 新增华为杯 Prompt 哈希；⑥ 本 README 3.4 节技能表补 `math-paper-huawei` 与 `imagegen` 行、说明目录计数 15→18。
- 主要文件：`.dsh/skills/math-paper-huawei/`（SKILL.md、mathmodel-card.yml、agents/openai.yaml、README.md、assets/templates/main.tex、laTeX-模板-GMCMthesis/ 四个年份文件、scripts/checks/ 七个脚本、scripts/plotting/python_flowchart.py）；`plugins/dsh-mathmodel/`（src 与 lib 的 cards/registry.js、lib/skills/catalog.js、test/ 四个测试 + card-snapshots.json）；`README.md`。华为杯优秀论文目录仅登记引用，未做任何改写。
- 官方冲突面：无官方源码、插件 API 或 UI 修改；仅在本地插件注册表与既有测试名单中新增条目，卡片协议仍为 `dsh.mathmodel.card/v1`。
- 安全边界：未触碰凭据、`.env`、论文工作区或运行中的服务；优秀论文仅作只读对标，卡片 Prompt 不含任何论文原文。
- 验证：`npm run build`（30 个文件）；`npm test` **109/109**（新增华为杯卡片 schema、默认值 `competition_language=中文`/`figure_total=15`/`body_pages=16`、Prompt 快照稳定、手动目录恰好 12 项、说明摘要含"华为杯"）；`xelatex example.tex` 成功产出 16 页 PDF（仅 hyperref 书签常规警告，无错误）。
- 回滚：删除 `.dsh/skills/math-paper-huawei/` 中新建文件并恢复被改脚本为 math-paper-cn 基线，插件侧移除 4 处华为杯注册行与快照条目后重新 `npm run build`；模板年份改动可按本记录反向改回；不涉及官方 Harness 文件。

### GOAL-20260818-38：官方 Harness 升级 `0.1.0-rc.6 → 0.1.0-rc.7`（预演先行、最小入侵）

- 时间：**2026-08-18（GOAL-37 之后）**
- 原因：上游 `deepseek-ai/deepseek-harness` 发布 `0.1.0-rc.7`，用户要求按"先预演、再更新、最小入侵、禁止改坏"的流程把本地工作区升级到 rc.7，同时保持全部本地改造（插件、Preset、Skill、Profile patch、皮肤、品牌）可用。
- 预演：npm pack 下载 rc.7 全部关键客户端包（conversation/runtime/input-trigger/api-remotes/base/web-app/ui-cordis/ui-skill/settings/ui-slots/skill/session-log-export 等 13+ 包）到 `Overall-goal/goal-4/preview/` 解包比对，逐项核对 **R1–R18 兼容矩阵 18/18 全绿**（结论 `Overall-goal/goal-4/preview-report.md`）：卡片 DOM 插槽、`conversation.session.header.utilities`、`_sessionLogButton` 类名、`conversation.input.*`、Typert Remote 服务命名、凭据服务、`enableRunInBackground → backgroundMode` 配置键迁移等全部确认；唯一需同步点为本地两个 Preset 的 4 行配置键。
- 修改：① 全局 `npm install -g @deepseek-ai/dsh@0.1.0-rc.7`；② `plugins/dsh-mathmodel/package.json` peerDependencies 与 2 个 dependencies 升至 `0.1.0-rc.7`（description 同步）；③ `src/version.js`（及 lib 副本）版本门 `SUPPORTED_DSH_VERSION` 升至 rc.7，`test/version.test.mjs` 断言同步；④ `.dsh/.agent-presets/mathmodel/agent.cordis.yml` 与 `imagegen/agent.cordis.yml` 的 `enableRunInBackground: false` → `backgroundMode: one-shot`（对齐上游 rc.7 配置键）；⑤ 本 README 头部基线与插件 README 基线描述。官方包、`node_modules` 官方区域、其他本地改造零改动。
- 主要文件：`plugins/dsh-mathmodel/package.json`、`plugins/dsh-mathmodel/src/version.js`、`plugins/dsh-mathmodel/test/version.test.mjs`、`.dsh/.agent-presets/mathmodel/agent.cordis.yml`、`.dsh/.agent-presets/imagegen/agent.cordis.yml`、`README.md`、`plugins/dsh-mathmodel/README.md`。备份与 SHA-256 清单见 `Overall-goal/goal-4/backup/`。
- 官方冲突面：仅版本门与依赖坐标更新，无 API/DOM 适配逻辑改动；rc.7 官方行为变化两条已确认并接受——(a) blank 新会话隐藏会话 header（Session log 按钮只在非空会话渲染，属官方 rc.7 变化）；(b) `/math-paper-cn` 输入先出官方技能菜单，Enter 选中后才弹插件卡片（rc.6 为直接弹出）。
- 安全边界：升级前停止 3080 服务并完成备份；未触碰凭据、`.env`、便携版产物（`dist/` 仍为 rc.6 运行时，未重建）；全程未删除任何本地脚本。
- 验证：插件 `npm run build` + `npm run check` + `npm test` **全绿（≥109 用例）**；Profile `pnpm install --offline` + `pnpm peers check` 通过；`dsh --profile web --dump-config` 确认 `dsh-mathmodel` 挂载、官方 `ui-skill` 仍禁用；重启 3080 后浏览器 E2E 全过——品牌 `MetaMathHARNESS`、大道至简标题图（`dsh-mm-hero-title-img`）、技能说明按钮、`/math-paper-cn` 卡片→确定→草稿写入 958 字符且未自动发送、非空会话 Session log 按钮（`nL4_yW_sessionLogButton`，插件 aria-label 覆盖"下载会话日志"生效）、控制台 0 错误（证据 `Overall-goal/goal-4/evidence/`）。
- 回滚：`npm install -g @deepseek-ai/dsh@0.1.0-rc.6`，按 `Overall-goal/goal-4/backup/` 清单恢复 package.json/version.js/test/两个 Preset，重新 `npm run build && npm test` 与 Profile `pnpm install --offline && pnpm peers check` 后重启 3080。

升级或重新物化 `.dsh/profiles/web/node_modules` 后，先在插件目录执行 `npm run build`，再在 Profile 目录执行以下命令，确保外置插件继续直接指向项目源码，而不是被生成目录中的旧副本覆盖：

```powershell
Set-Location F:\DeepSeekHarness\.dsh\profiles\web
pnpm link F:\DeepSeekHarness\plugins\dsh-mathmodel
```

### GOAL-20260818-39：MetaMath Harness 公开发布（gh CLI 上传、仓库树同步 rc.7、skill 重写为公开发布）

- 时间：**2026-08-18 19:35:07 +08:00（GOAL-38 之后）**
- 原因：GOAL-38 产出净化归档后，用户授权用 GitHub CLI 上传并明确要求仓库 `LKQ667/metamath-harness` 保持公开（保住 star）；随后发现仓库文件树停留在 8/17 rc.6 时代（缺 math-paper-huawei 技能全量、插件 rc.7 版本门未同步）且首页看不到收款码，要求仓库与最新代码一致；并要求把上述流程固化为 `metamath-private-release` skill 的新边界（公开仓库、gh CLI 推送、快捷方式验证、收尾清理）。
- 修改：① skill 重写：`.codex/skills/metamath-private-release/SKILL.md` 由"私有发布"改为"公开发布"（PUBLIC 硬边界禁止转私、gh CLI 推送流程、LF 归一化比对、桌面快捷方式验证链、清理双向清单），同步全局副本 `~/.trae-cn/skills/metamath-private-release/SKILL.md`；② 仓库操作：仓库保持 PUBLIC，README 更新为 rc.7 版（commit `fad4245`），Release v0.1.1 旧 rc.6 资产删除并替换为 rc.7 ZIP（49,085,381 字节，SHA-256 `63D1A99B...9D6D6A`）；③ 仓库树同步：git blob SHA + LF 归一化比对识别真实差异 33 个 + 新增 130 个（math-paper-huawei 技能全量与品牌图），经 git data API（163 blobs → 单 tree → 单 commit `c24ec32`）单提交同步，刻意跳过 `plugins/dsh-mathmodel/lib/`（.gitignore 构建产物约定）与 `__pycache__`；④ 仓库 README 新增"捐赠支持"章节内嵌展示收款码（commit `53fcc8`）。
- 主要文件：`.codex/skills/metamath-private-release/SKILL.md`、全局 skill 同名副本、`Overall-goal/goal-4/tasks.md`（补录台账）；远端为 GitHub 仓库 README/Release 资产/文件树。
- 官方冲突面：无官方源码、插件 API 或 UI 修改；gh CLI 操作仅限 `LKQ667/metamath-harness` 仓库。
- 安全边界：ZIP 经打包前、解压后两次脱敏预检 clean 才上传；全程未提交凭据、会话、缓存或本机路径；下载回读哈希与本地一致后才报告完成。
- 验证：仓库可见性 public 回读；Release 资产 `state=uploaded` 且远程下载 SHA-256 与本地一致；同步后 LF 归一化双向比对 730 blobs 零差异；收款码两文件在仓库根目录且 README 内嵌展示；桌面快捷方式 `E:\Desktop\MetaMath Harness.lnk` 链路验证（.lnk → 启动脚本 → PATH dsh → 全局包 `0.1.0-rc.7`）。
- 回滚：两份 SKILL.md 按旧版恢复；远端可按 commit `c24ec32`/`53fcc8`/`fad4245` 反向补丁恢复仓库树与 README，并重传旧 ZIP；不涉及官方 Harness 文件。

### GOAL-20260818-40：math-paper-huawei 正文页数硬约束（大于 25 页）

- 时间：**2026-08-18 19:35:07 +08:00（GOAL-39 之后）**
- 原因：用户硬约束"正文（除附录和代码部分）页数必须大于 25 页"，要求把该约束落入 math-paper-huawei 技能门禁并严格测试，替换原"16–20 页质量目标/官方不超过 20 页"表述。
- 修改：`scripts/checks/check_body_page_count_minimum.py` 的 `DEFAULT_TARGET` 16→26（"大于 25 页"= 至少 26 页），docstring/帮助文本/错误消息同步，用户 README 目标提升逻辑保留（取 max）；`SKILL.md` 两处（`body_pages` 锁定字段说明、正文页数硬约束条目）；`mathmodel-card.yml` `body_pages` default/min 26 并加硬约束说明；`references/auto-checklist.md` 两处清单项；`assets/templates/main.tex` 两处模板注释；插件侧 `test/first-party-cards.test.mjs` 断言 `body_pages=26`、`test/card-snapshots.json` 华为杯 Prompt 哈希更新（`54f72d45...`）。共 7 文件 10 处。
- 主要文件：`.dsh/skills/math-paper-huawei/`（SKILL.md、mathmodel-card.yml、references/auto-checklist.md、assets/templates/main.tex、scripts/checks/check_body_page_count_minimum.py）；`plugins/dsh-mathmodel/test/first-party-cards.test.mjs`、`plugins/dsh-mathmodel/test/card-snapshots.json`。
- 官方冲突面：无官方源码修改；插件运行时直接读技能 `mathmodel-card.yml`，无重复默认值，仅测试断言与快照跟进。
- 安全边界：未触碰凭据、运行中服务与其他 Skill；历史 GOAL-37 记录中的 `body_pages=16` 为当时事实，保持不动。
- 验证：真实检查器边界测试 6/6（25 页拒、26 页过、用户目标 28 时 26 拒 28 过、旧"不少于 16"配置不再放行 16 页、附录跳页仍拒）；技能回归 54/54（checks 44 + latex 10）；插件 `npm test` 109/109；全目录 grep 零旧页数残留；临时测试脚本已删除。
- 回滚：`DEFAULT_TARGET` 改回 16 并按本记录反向恢复 7 文件 10 处，重跑插件 `npm test` 与边界测试确认回到基线。

### GOAL-20260818-41：接入第三方订阅插件 dsh-plugin-subscriptions 并公开发布

- 时间：**2026-08-18 20:41:31 +08:00（GOAL-40 之后）**
- 原因：用户要求把 `https://github.com/V1ki/dsh-plugin-subscriptions`（ChatGPT/Claude/Grok 订阅作为 LLM provider）接入项目且不与本地改造冲突，随后按 metamath-private-release skill 流程公开发布最新代码。
- 修改：① 安装：`dsh plugin --profile web add dsh-plugin-subscriptions`（npm 0.3.1 预构建；作者 devDeps 全为本机绝对路径 link，本地构建不可行）；② 冲突修复一：`dsh plugin add` 物化 bundle 层后与本地 patch 层的 `ui-skins` 条目重复（`duplicate loader entry id: ui-skins` 启动失败），从 `package.json` 的 `dsh.profile.bundles` 移除 `dsh-client-ui-skins`，皮肤回归本地手工接线；③ 冲突修复二：插件 codex 路由注册全局工具 `image_generate` 与 `mathmodel-tools` 同名（后注册方启动失败），在 `cordis.patch.yml` 对 `llm-subscriptions` 覆盖 `providers: [claude, grok]` 禁用 codex 路由，保留本地 API 生图工具；④ 主 README 新增 3.3 节接线职责一行与 3.3a 节插件专述（来源、安装方式、两处冲突处置、peer 兼容结论）。
- 主要文件：`.dsh/profiles/web/package.json`、`.dsh/profiles/web/cordis.patch.yml`、`.dsh/profiles/web/pnpm-lock.yaml`、`README.md`；安装前备份 4 文件于 `Overall-goal/goal-4/backup/before-subscriptions-20260818/`。
- 官方冲突面：不改官方源码；`dsh plugin add` 属官方安装命令；peerDependencies `^0.1.0-rc.5` 与 rc.7 兼容，peers 警告与既有 skins 插件同模式（官方 bundle 运行时提供）。
- 安全边界：插件 token 存用户主目录 `~/.dsh/plugins/subscriptions/auth.json`（插件自管，0600），本项目源码、仓库与归档不含任何 token；未登录任何 provider，发布内容零凭据。
- 验证：`dump-config` 四插件挂载正确（llm-subscriptions/mathmodel/mathmodel-tools/ui-skins）；服务 3080 重启 READY；浏览器 E2E：Settings → 订阅页三个 provider 卡片与登录按钮、MetaMath 品牌 SVG 182x24、"大道至简"主区标题、输入框、console 零错误（两轮 DOM 细查确认首轮 subagent 的品牌误报为选择器问题）。
- 回滚：恢复备份 4 文件并 `pnpm install`；如需彻底卸载再执行 `dsh plugin --profile web remove dsh-plugin-subscriptions`。

### GOAL-20260818-42：原生 ChatGPT 订阅生图连接 codex-subscription（dsh-llm-oauth + 第五类连接）

- 时间：**2026-08-18 21:39:34 +08:00（GOAL-41 之后）**
- 原因：用户要求基于 `https://github.com/ziyou979/dsh-llm-oauth` 采用原生适配器方案，给 `dsh-mathmodel` 增加第五类生图连接 `codex-subscription`——完全原生（token 自动刷新、统一连接管理 UI、无外部服务），替代 sub2api 网关中转；流程要求先制定计划与预演、严谨小幅度优化、严格测试通过后才更新仓库。
- 预演：方案与风险清单见 `Overall-goal/goal-5/plan.md`——通读 dsh-llm-oauth 源码（无工具注册、inject 仅 llm、凭据 pi-ai-oauth.json 格式与刷新协议）、pi-ai 0.84.2 credential 结构、V1ki codex.ts 生图端点（`chatgpt.com/backend-api/codex/images/generations`、`originator: codex_cli_rs`、401 强刷重试）与本地连接体系四件套（adapters/connections/image-connections/service），确认适配器签名不变、verify/service/tools/host 零改动。
- 修改：① 新增 `src/image/codex-auth.js`（~135 行：DSH_HOME 解析与 dsh-llm-oauth 一致、读-改-写仅替换 `openai-codex` 条目、form-encoded refresh grant、JWT 解 accountId、<5 分钟预刷新、describe 不含秘密）；② `src/image/adapters.js` 新增 `codexImagesAdapter`（会话快照或凭据直解、count>1 循环、参考图拒绝、401 强刷重试一次）并注册 `codex-images`；③ `src/security/image-connections.js` 新增 `codex-subscription` 模板（固定 Base URL 不可编辑、专属适配器、草稿校验）与订阅凭据 describe 特例；④ `src/image/connections.js` describe/resolve/setKey/clearKey 五处 codex 特例分支 + `codexHome` 测试注入；⑤ `src/client-bundle.cjs` 模板 meta（"ChatGPT 订阅"）+ 适配器 label（"Codex 订阅生图"）+ 该模板隐藏 API Key 输入与"清除 Key"按钮；⑥ `scripts/build.mjs`、`src/index.js` 导出、`package.json` check 脚本跟进；⑦ 新增 `test/codex-subscription.test.mjs` 全链路单测（mock fetch 零真实网络）。
- Profile 侧：安装 `dsh plugin --profile web add github:ziyou979/dsh-llm-oauth`（pnpm-workspace.yaml `allowBuilds` 放行 git prepare 构建，`@google/genai`/`protobufjs` 传递依赖脚本显式 false）；`dsh plugin` reconcile 自动把 `dsh-llm-oauth` 与 `dsh-client-ui-skins` 加入 bundles——后者与 patch 层手工 insert 同 id 双插导致启动失败（`duplicate loader entry id: ui-skins`），处置为从 `cordis.patch.yml` 移除手工 insert、皮肤改为 bundle 层自激活（比 GOAL-41 的反向处置更符合 reconcile 自动维护语义）；`cordis.patch.yml` 对 `llm-oauth` 覆盖 `catalog: [openai-codex]`。
- 主要文件：`plugins/dsh-mathmodel/src/image/codex-auth.js`（新）、`plugins/dsh-mathmodel/test/codex-subscription.test.mjs`（新）、`plugins/dsh-mathmodel/src/image/adapters.js`、`src/image/connections.js`、`src/security/image-connections.js`、`src/client-bundle.cjs`、`src/index.js`、`scripts/build.mjs`、`package.json`；`.dsh/profiles/web/package.json`、`cordis.patch.yml`、`pnpm-workspace.yaml`、`pnpm-lock.yaml`；`README.md`。改动前备份于 `plugins/dsh-mathmodel/.backup-goal5/`。
- 官方冲突面：不改官方源码；`dsh plugin add` 属官方安装命令；llm-oauth 默认休眠且不注册工具，与 `llm-subscriptions`（claude+grok）路由无重叠，与 `mathmodel-tools` 的 `image_generate` 零冲突。
- 安全边界：token 只落 `$DSH_HOME/pi-ai-oauth.json`（与 dsh-llm-oauth 共享，读-改-写保留其他 provider 条目）；错误消息不含 token；未登录任何 provider，发布内容零凭据；ChatGPT 订阅生图为非官方端点，模板 hint 与 3.3b 节均明示账号限制风险。
- 验证：插件 `npm run check` + `npm test` **119/119 全绿**（新增 codex 单测 10 项：accountId 解析、读写隔离、刷新协议与错误分类、会话解析、describe 无秘密、模板校验、适配器请求头/b64/count/参考图拒绝/401 强刷）；`dump-config` 确认 llm-oauth（catalog 仅 openai-codex）/llm-subscriptions（claude+grok）/mathmodel/mathmodel-tools/ui-skins 单例挂载；3081 端口新实例浏览器 E2E：设置 → 模型 → 生图模型 → 模板选择器出现"ChatGPT 订阅"，选中后无 API Key/Base URL 字段、接口格式"Codex 订阅生图"、提示正确；OAuth / 订阅页仅 OpenAI Codex 登录卡片、凭据路径 `F:\DeepSeekHarness\.dsh\pi-ai-oauth.json` 正确；console 零新增错误（截图 `goal5-oauth-page.png`）。
- 回滚：`dsh plugin --profile web remove dsh-llm-oauth` 并恢复 `cordis.patch.yml` 的 ui-skins 手工 insert；插件侧按 `.backup-goal5/` 恢复 6 个文件后 `npm run build && npm test`；README 按本记录反向恢复。
- 后续：用户重启 3080 服务后，在 OAuth / 订阅页完成 openai-codex 设备码登录（ChatGPT 需先开启设备码授权入口），即可在生图模型区新建"ChatGPT 订阅"连接并真实测试。

### GOAL-20260819-43：数学建模卡片 Prompt 注入 Goal 激活首条指令（修复概率不触发）

- 时间：**2026-08-19 12:09:28 +08:00（GOAL-42 之后）**
- 原因：用户反馈数学建模模式下 goal 存在概率不触发——根因是 goal 激活只依赖 SKILL.md 里的模型侧软指示（`run_to_pdf=true 时先调用 get_goal；无 Goal 时调用 create_goal`），长上下文下模型偶尔忽略。用户建议在提示词直接加入 `/goal` 命令。
- 预演（方案否决与修正）：通读官方 `dsh-command-goal` 与 Web 命令适配器源码确认字面方案不可行——`onEnter` 对以 `/` 开头的整条 draft 走命令仲裁，`/goal` 作为 leadingInput 命令会 claim 全部剩余文本作为 objective（`parseGoalCommand` 把非控制词输入整体当目标），且官方 README 明确"斜杠输入不进入模型请求"：`/goal` 前缀会把 `/math-paper-cn` + JSON 整体吞进 goal objective，正文不发给模型，比概率不触发更糟。修正方案：把 goal 激活指令注入**用户消息正文**（`renderCardPrompt` 生成的"执行要求"第一条）——模型对用户消息正文指令的遵从率接近确定，`/math-paper-cn` 首行触发链路与 JSON 结构完全不动。
- 修改：`plugins/dsh-mathmodel/src/cards/prompt.js` 一处——`run_to_pdf === true` 时在 instructions 首位插入"首轮动作：先调用 get_goal 检查当前会话 Goal；当前会话无 Goal 时立即调用 create_goal，objective 固定为持续完成论文并交付 PDF；已有同一目标则继续推进、禁止覆盖"；`test/first-party-cards.test.mjs` 新增专项测试（三张论文卡片首条即 goal 指令、`run_to_pdf=false` 不注入、无该字段卡片不受影响）；`test/card-snapshots.json` 同步三张论文卡片新哈希（math-paper-cn `57ccca1a…`、huashu `1fce50d2…`、huawei `5e87af9a…`）。
- 主要文件：`plugins/dsh-mathmodel/src/cards/prompt.js`、`test/first-party-cards.test.mjs`、`test/card-snapshots.json`；改动前备份于 `plugins/dsh-mathmodel/.backup-goal6/`。
- 官方冲突面：不改官方源码；改动仅在本插件卡片渲染层，客户端、host、preset 零改动。
- 验证：`npm run check` 通过；`npm test` **120/120 全绿**（新增 1 项 goal 指令专项）；重启 3080 后浏览器 E2E：数学建模模式 → `/math-paper-cn` 卡片 → 确认（仅写入草稿）→ 草稿"执行要求"第一条即 goal 激活指令、`/math-paper-cn` 仍居首、JSON 结构不变；console 零错误。
- 回滚：按 `.backup-goal6/prompt.js` 恢复源码并还原快照/测试文件后 `npm run build && npm test`。
- 后续：三个论文 Skill（math-paper-cn/huashu/huawei）共用此机制；关闭卡片"全自动持续到最终 PDF"开关即可不注入 goal 指令。

### GOAL-20260819-44：订阅与自定义提供方上下文窗口官方值修复（Grok catalog 覆盖 + settings.yaml 逐模型填写）

- 时间：**2026-08-19 15:30:00 +08:00（GOAL-43 之后）**
- 原因：用户发现订阅与自定义提供方的上下文窗口都只有 200 多 k——Grok 插件因本机无法访问 `cli-chat-proxy.grok.com`（ECONNRESET）自动发现失败，全部模型回退默认 256k（grok.js 的 `GROK_CONTEXT_WINDOW = 256_000`）；自定义提供方（llm-pi-ai 分节）多数模型未填 `contextWindow`，走 256k 级默认值。要求全部数值来自官方渠道，禁止编造。
- 预演（官方数值核实）：Grok——真实请求 `api.x.ai/v1/models` 实测 7 模型 `context_length`（4.20 系/4.3 = 1,000,000、4.5/4.6 = 500,000、build-0.1 = 256,000）；其余取各家官方文档：DeepSeek V4 全系 1M（api-docs.deepseek.com）、GLM 5.3/5.2 = 1M 与 5.1 = 200K（docs.bigmodel.cn）、Kimi K3 = 1M 与 K2.7 Code/K2.6 = 256K（platform.kimi.com）、MiMo V2.5/V2.5-Pro = 1M（mimo.mi.com）、GPT-5.6 全系 1,050,000（developers.openai.com）、hy3 = 256K（腾讯云 TokenHub）、seed-2.1 = 262,144、minimax-m2.x = 200K、qwen3.7/3.8-max = 1M。
- 修改①（方案 2，Grok 订阅）：`cordis.patch.yml` 对 `llm-subscriptions` 追加 `models.grok` 覆盖——7 个模型逐个填官方 `contextWindow` 与 `inputModalities: [text, image]`（后者为插件 zod schema 必填，首版漏填导致服务启动失败，已修复）；配置后插件关闭自动发现，直接采用静态目录。
- 修改②（方案 1，自定义提供方）：`.dsh/settings.yaml` 的 `llm-pi-ai.providers` 下 5 个提供方（volcengine-agent、tokenrhythm、sub2api、opencode-rt、volcengine-coding）逐模型补 `contextWindow`，各提供方头部与文件内均注释官方来源；涉及 DeepSeek V4、GLM、Kimi、MiMo、hy3、GPT-5.6、qwen、minimax、seed 等约 30 个模型条目。
- 主要文件：`.dsh/profiles/web/cordis.patch.yml`、`.dsh/settings.yaml`；`README.md` 3.3a 节同步补充 Grok 覆盖说明。
- 官方冲突面：不改官方源码与插件代码；全部为声明式配置覆盖（`models.grok` 为插件 zod schema 预留的覆盖口子）。
- 安全边界：仅改模型目录数值，不触碰凭据（`.dsh/.credentials.yaml`）、OAuth token 与运行中服务的其他配置；无新增网络依赖（api.x.ai 探测用已有订阅凭据）。
- 验证：临时脚本 `.release-staging/ctx-verify.mjs` 解析两份 YAML 并与官方值逐一比对——Grok 7 模型全部一致、settings.yaml 全部 contextWindow 与官方来源一致、`providers=[claude,grok]` 未变；服务 3080 重启（PID 23660，15:06:36 启动，晚于两配置文件 mtime 15:06:23/15:02:57）后持续 HTTP 200，zod 校验通过（服务未崩溃即 schema 合法）。
- 回滚：删除 `cordis.patch.yml` 中 `llm-subscriptions.config.models.grok` 块（自动发现恢复，网络通时目录自动恢复）；移除 `settings.yaml` 各模型 `contextWindow` 字段及来源注释；README 按本记录反向恢复。
- 清理：删除本次任务临时脚本 4 个（`.release-staging/ctx-verify.mjs`、`ctx-probe-all.mjs`、`provider-catalog-probe.mjs`、`grok-catalog-probe.mjs`）及根目录 `.tmp-*` 临时文件与执行截图；保留 `metamath-harness-v0.1.1.zip`、`goal5-oauth-page.png`（台账证据）与全部 `.backup-*` 回滚备份。

### GOAL-20260819-45：原生 Grok 订阅生图连接 grok-subscription（第六类连接）

- 时间：**2026-08-19 16:33:00 +08:00（GOAL-44 之后）**
- 原因：用户要求参考 `https://github.com/V1ki/dsh-plugin-subscriptions` 适配 Grok 订阅生图——复用订阅插件的 Grok OAuth 会话（`plugins/subscriptions/auth.json`）实现无需 API Key 的原生生图连接，与 GOAL-42 的 codex-subscription 同构。
- 预演：通读 `llm-subscriptions` 插件的 Grok 会话结构（access/refresh/expiresAt、auth.x.ai 刷新端点）与 xAI 官方 Images API 文档（`api.x.ai/v1/images/generations`，模型 grok-imagine-image/image-2.0/image-quality，返回 b64_json 或 url），确认与 codex-subscription 的适配器签名一致、verify/service/tools/host 零改动。
- 修改：① 新增 `src/image/grok-auth.js`（会话读取/刷新/写回、<5 分钟预刷新、describe 不含秘密）；② `src/image/adapters.js` 新增 `grokImagesAdapter`（会话快照或凭据直解、count>1 循环、参考图拒绝、401 强刷重试一次、b64_json/url 双格式解析）并注册 `grok-images`，附带修复 codexImagesAdapter 同源的 token 属性名不一致 bug（快照 `access` vs 会话 `accessToken`，新增统一取值 helper）；③ `src/security/image-connections.js` 新增 `grok-subscription` 模板（固定 Base URL 不可编辑、专属适配器、默认模型 grok-imagine-image）；④ `src/image/connections.js` describe/resolve 特例分支 + `grokHome` 测试注入；⑤ `src/client-bundle.cjs` 模板 meta（"Grok 订阅"）+ 适配器 label（"Grok 订阅生图"）+ 隐藏 API Key 输入；⑥ `scripts/build.mjs`、`src/index.js` 导出、`package.json` check 脚本跟进；⑦ 新增 `test/grok-subscription.test.mjs` 全链路单测（mock fetch 零真实网络）。
- 主要文件：`plugins/dsh-mathmodel/src/image/grok-auth.js`（新）、`plugins/dsh-mathmodel/test/grok-subscription.test.mjs`（新）、`plugins/dsh-mathmodel/src/image/adapters.js`、`src/image/connections.js`、`src/security/image-connections.js`、`src/client-bundle.cjs`、`src/index.js`、`scripts/build.mjs`、`package.json`；`README.md`。
- 官方冲突面：不改官方源码与订阅插件代码；仅读取其凭据文件格式（读-改-写只替换 grok 条目，保留其他 provider）。
- 安全边界：token 只落订阅插件的 `plugins/subscriptions/auth.json`（插件自管，0600）；错误消息不含 token；E2E 验证后临时脚本已删除，发布内容零凭据。
- 验证：插件 `npm run check` 通过；`npm test` **130/130 全绿**（新增 grok 单测 10 项：会话解析、刷新协议、describe 无秘密、模板校验、适配器请求头/b64/url 双格式/count/参考图拒绝/401 强刷后授权头逐次断言）；真实 API E2E 验证通过（凭据解析 → 图片生成全链路）；服务 3080 重启后加载新插件，HTTP 200。
- 回滚：删除新增两文件并按 git/备份恢复其余 7 文件后 `npm run build && npm test`；README 按本记录反向恢复。
- 后续：在 Settings → 订阅页完成 Grok 登录后，即可在生图模型区新建"Grok 订阅"连接使用。
- 发布：metamath-private-release 流程——staging 全量同步本地最新（37 文件）+ 预检修复 12 处误报源（README 4 处本机路径规范化、3 份 auto-checklist 与 9 个检查脚本正则改字符类写法、2 个测试 fixture 缩短假 token）后预检 clean（765 文件零 findings）；LF 归一化比对识别真实差异 33 个（新增 2 + 修改 31，含 GOAL-43/44 未发布改动），git data API 单提交 `1f7e122` 推送；补推 README 恢复"许可 + 捐赠支持"章节（历史重写中丢失，收款码需内嵌展示）commit `c9c88b9`；回读核验 public、864 blobs 零差异、收款码内嵌；插件 `npm test` 修复后 130/130 复验全绿；桌面快捷方式链验证（.lnk → 启动脚本 → PATH dsh → 全局包 0.1.0-rc.7）。

## 5. 日常启动与验证

### 5.1 便携版

正式产物位于 `dist/DeepSeekHarness-portable-win-x64/` 和同名 ZIP。ZIP 为 **2.61 GiB**，解压后 **2.57 GiB**；低于原 4–7 GB 估算且功能门禁完整，未通过填充文件扩大包体。SHA-256 为 `4264fd90b9dddbfccdede2642c58362f233f1f6cc2e1d301bb35f23821da425f`。

```powershell
# 构建前只检查目标盘至少有 20 GB 临时空间；不会预分配 20 GB
.\构建便携版.ps1 -ReuseCache

# 解压后启动或自检
.\启动-DeepSeek-Harness.cmd
.\依赖自检.cmd
```

运行时固定为 Node.js 24.12.0、Harness 0.1.0-rc.6、Python 3.12.3、TeX Live 2026、Draw.io 31.1.5 与 Poppler 26.05.0；Python 包的精确版本、来源、许可证和哈希见 `portable/runtime-manifest.json` 与产物内 `RELEASE-MANIFEST.json`。构建只在 staging、秘密扫描、自检、体积硬门和 ZIP 解压复测全部通过后发布；7–8 GB 生成组件报告，超过 8 GB 失败。

升级时先在新的 staging 下载并校验运行时，完成全部自检后再替换 `app/` 与 `runtime/`；始终保留 `data/`。失败时恢复旧版 `app/`、`runtime/` 或旧 ZIP。中文/空格解压路径会创建临时盘符别名，仅供子进程使用，Harness 退出后自动清理。

### 5.2 开发工作区

启动 Web：

```powershell
Set-Location F:\DeepSeekHarness
dsh web --host 127.0.0.1 --port 3080
```

日常建议直接使用 Windows 的 MetaMath Harness 快捷入口。快捷入口会复用已运行的 3080 服务；首次冷启动会隐藏等待服务就绪，不需要手动操作终端。若启动失败，查看：

```text
%LOCALAPPDATA%\DeepSeekHarness\logs\web.stderr.log
```

浏览器打开 `http://127.0.0.1:3080`，选择“数学建模模式”，输入 `/math-paper-cn`。卡片确认后，结构化 Prompt 应留在输入框中，必须由用户手动发送。

插件验证：

```powershell
Set-Location F:\DeepSeekHarness\plugins\dsh-mathmodel
npm run check
npm test
npm run test:environment
npm run e2e:paper
```

Profile 验证：

```powershell
Set-Location F:\DeepSeekHarness\.dsh\profiles\web
pnpm install --offline
pnpm peers check

Set-Location F:\DeepSeekHarness
dsh --profile web --dump-config
```

当前验收基线：插件 73/73、环境预检 1/1、通用论文门禁 44/44、华数杯门禁 55/55、柱状图攻击矩阵两套各 9/9、真实 Draw.io/LaTeX E2E 通过；便携 ZIP 的中文空格路径离线验收通过；Web 控制台错误 0，服务 stderr 为空。

## 6. 官方升级前保护流程

### 6.1 先停止写入并记录版本

1. 停止正在运行的 `dsh web`。
2. 记录当前官方版本、Node.js、pnpm 和 npm 版本。
3. 确认本 README 已记录最后一次本地修改的时间、文件和验证结果。
4. 不要在正在升级的目录中直接试验覆盖操作。

### 6.2 只备份本地所有权文件

建议备份以下路径：

```text
README.md
plugins/dsh-mathmodel/
%APPDATA%\npm\dsh-assets\启动-DeepSeek-Harness.ps1
.dsh/.agent-presets/mathmodel/
.dsh/skills/<本 README 3.4 节列出的十二个 Skill>/
.dsh/profiles/web/package.json
.dsh/profiles/web/cordis.patch.yml
.dsh/profiles/web/pnpm-lock.yaml
.dsh/计划文档/
Overall-goal/
```

备份中不应包含 `.dsh/profiles/**/node_modules/`、官方安装目录、缓存和临时复制目录。旧 `.env` 属于敏感用户文件，不要复制到公开仓库或诊断包。

### 6.3 建立文件清单与哈希

升级前可在私有备份目录执行：

```powershell
$localPaths = @(
  'F:\DeepSeekHarness\README.md',
  'F:\DeepSeekHarness\plugins\dsh-mathmodel',
  'F:\DeepSeekHarness\.dsh\.agent-presets\mathmodel',
  'F:\DeepSeekHarness\.dsh\profiles\web\package.json',
  'F:\DeepSeekHarness\.dsh\profiles\web\cordis.patch.yml',
  'F:\DeepSeekHarness\.dsh\profiles\web\pnpm-lock.yaml'
)

Get-ChildItem $localPaths -File -Recurse |
  Get-FileHash -Algorithm SHA256 |
  Export-Csv '.\local-modifications.sha256.csv' -NoTypeInformation -Encoding UTF8
```

该清单用于确认本地源码是否完整，不用于把旧官方文件覆盖到新版。

## 7. 官方升级后的重接入流程

严格按以下顺序执行：

1. 先让新版官方 Harness 在没有本地插件的状态下正常启动。
2. 阅读官方版本说明，重点检查插件生命周期、Typert Remote、Slot、Input Trigger、Conversation 草稿接口、凭据服务、Preset roster、全局 CLI 入口路径，以及 Web Header/Session log 的 DOM 与无障碍属性。
3. 保留 `plugins/dsh-mathmodel/src/`，根据新版 API 修复兼容性；不要先放宽 `src/version.js` 的版本门。
4. 重新比较新版官方 `standard` roster，再调整用户 `mathmodel` Preset。
5. 在新版 Web Profile 上重新应用最小 `package.json` 本地依赖和 `cordis.patch.yml`，不要整文件覆盖。
6. 重新安装 Profile 依赖；不要复用旧 `node_modules`。
7. 依次运行 `npm run check`、`npm test`、`npm run test:environment`、论文 E2E、Peer 检查和 dump-config。
8. 真实浏览器复测普通 Skill、卡片 Skill、零发送草稿、右上角说明、非空会话保护和控制台错误；同时确认 Session log 选择器唯一命中、官方下载功能仍可用、两个图标同排且 `aria-label/title` 正确。
9. 复核第 3.8 节快捷启动器：分别测试“3080 已运行”和“完全冷启动”，确认无 Terminal 黑窗、无提前失败弹窗、日志路径有效。
10. 全部通过后才更新 `src/version.js` 中允许的官方版本，并在本 README 追加新的带时间 goal 记录。

如果任一步失败，保持外置插件禁用，让新版官方 Harness 先可用；不得用旧官方包回填新版环境来掩盖兼容问题。

## 8. 快速回滚

### 8.1 仅回滚官方 Session log 覆盖

如果官方升级后只有顶部图标适配失效，应优先定向回滚，不要先删除 Skill 或其他 Mathmodel 功能：

1. 在 `plugins/dsh-mathmodel/src/client-bundle.cjs` 中移除 utilities 插槽下 `_sessionLogButton` 的覆盖 CSS。
2. 移除 `MathmodelInfo` 中设置/恢复“下载会话日志”属性的 effect。
3. 把技能说明入口重新放到不会侵入官方 Header 的独立位置。
4. 执行 `npm run check`、`npm test`、`npm run build`，重启 Web。
5. 验证官方 `Session log` 文案、下载行为和无障碍名称完全恢复为新版官方实现。

不得通过修改官方 bundle、复制旧版 Header 组件或使用更宽泛的全局 CSS 选择器来维持旧外观。

### 8.2 停用整个 Mathmodel 插件

回滚不需要删除插件或 Skill。在 `.dsh/profiles/web/cordis.patch.yml` 中恢复官方 Skill UI，并禁用外置插件：

```yaml
- id: ui-skill
  name: '@deepseek-ai/dsh-client-ui-skill'
  disabled: false

- insert:
    - id: mathmodel
      name: '@deepseek-harness/dsh-mathmodel'
      disabled: true
```

然后重启 `dsh web`，验证官方模式和普通 Skill。确认官方功能恢复后，再单独处理本地插件兼容问题。

禁止使用以下回滚方式：

- 删除整个 `.dsh/skills`。
- 把旧 `.dsh` 整目录覆盖到新版。
- 把旧 `node_modules` 复制到新版 Profile。
- 直接修改官方 Client、官方 Preset 或全局安装包来绕过错误。

## 9. 后续修改记录范式

以后每次修改都在“goal 修复记录”末尾追加，不删除历史项。使用下面的固定格式：

```markdown
### GOAL-YYYYMMDD-NN：简短标题

- 时间：**YYYY-MM-DD HH:mm:ss +08:00**
- 原因：为什么需要修改。
- 修改：实际改变了什么行为。
- 主要文件：只列本次真正修改的本地所有权文件。
- 官方冲突面：升级时需要重点复测的官方接口或配置。
- 安全边界：凭据、发送、付费、文件或系统方面的限制。
- 验证：实际运行的测试、浏览器检查和结果。
- 回滚：如何只停用或恢复本次修改，不伤害官方安装。
```

记录规则：

- 时间必须包含日期、时分秒和 `+08:00`。
- “修改”必须对应真实文件，禁止只写“优化”“修复若干问题”。
- 测试未运行时必须写“未验证”，不能写“通过”。
- 版本变化必须记录旧版、新版和版本门调整原因。
- 凭据值、Token、`.env` 内容和个人隐私不得写入记录。
- 生成物只记录生成命令，源码变更必须指向 `src/` 或 Skill 源文件。

## 10. 当前维护结论

当前 `mathmodel` 改造与官方 DeepSeek Harness 保持外置隔离：官方包和官方 Preset未被修改，本地逻辑集中在插件、用户 Preset、目标 Skill 和 Web Profile 最小接线中。后续官方升级应以“新版官方环境优先、本地插件重新适配”为原则，绝不能用旧官方文件覆盖新版。

## 11. 许可

`plugins/dsh-mathmodel` 为 MIT；其余配置与脚本基于 DeepSeek Harness 插件范式编写，仅供学习与研究使用。

## 12. 捐赠支持

如果本项目对你有帮助，欢迎请作者喝杯咖啡：

| 支付宝 | 微信 |
|:---:|:---:|
| ![](donate-alipay.jpg) | ![](donate-wechat.jpg) |
