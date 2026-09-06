# Changelog

## 1.2.0 (2026-09-04)

### Changes

- 适配 DSH v0.1.2-rc.1 上游重构（`dsh-plugin-desktop` 2.0.5），同一份构建继续兼容 0.1.1 宿主：
  - `@deepseek-ai/dsh-settings` 在 0.1.2 的 npm 包中移除了 `settingsNamespace` / `installSettingsSection` 自由函数（桌面宿主内置兼容垫片，npm 安装没有；缺失导出会在 ESM 链接期直接报错）。设置接线改为双轨：从模块命名空间读取旧自由函数，存在则使用（0.1.1 宿主与带垫片的 0.1.2 桌面宿主），否则回退 `settings` 服务的 `installSection` 方法（无垫片的 0.1.2 npm 环境）；`TRAE_SETTINGS_NS` 改为字面量 `'trae'`。
  - `@deepseek-ai/dsh-client-runtime` 包在上游被拆分删除：客户端入口的 `ClientContext` 类型改从 `@deepseek-ai/cordis` 导入，`slots` / `settingsScope` / `locale` 服务类型分别通过 `dsh-client-ui-renderer/client`、`dsh-client-ui-settings/client`、`dsh-client-locale/client` 的类型增广获得；`package.json` 的 `dsh.client.inject` 相应把 `@deepseek-ai/dsh-client-runtime` 替换为 `@deepseek-ai/dsh-client-ui-renderer`（0.1.2 中 `slots` 服务的提供方，该包在 0.1.1 中同样存在）。
  - `llm.registerModelDiscovery` 的取消信号从 `request.signal` 移到回调第二个参数：发现回调改用 `(request, signal)` 签名并透传给 Trae 发现请求，修复 0.1.2 宿主下取消不再传播的问题；0.1.1 宿主回退读取 `request.signal`。
- devDependencies 升级至 `@deepseek-ai/dsh-*@0.1.2-rc.1`、`cordis@^4.0.2`、`schemastery@3.18.2`、`pi-ai@0.84.2`（新增 `dsh-client-ui-renderer`、`dsh-client-ui-settings`，移除已删除的 `dsh-client-runtime`），`pnpm run check` 现在直接面向 0.1.2 类型与运行时验证；`peerDependencies` 维持 `>=0.1.2-0 <0.2.0-0` 不变。

## 1.1.2 (2026-08-31)

### Fixes

- 对齐 DSH 宿主（`dsh-plugin-desktop`）实际提供的依赖版本，修正 `peerDependencies` 范围：`@deepseek-ai/dsh-*` 由 `^0.1.1-rc.2` 改为 `>=0.1.2-0 <0.2.0-0`（覆盖宿主 `0.1.2-alpha.1` 及 npm 预发布线），`@earendil-works/pi-ai` 由精确 `0.82.1` 放宽为 `>=0.82.1`（宿主为 `0.84.3`）。修复旧范围按 node-semver 预发布元组规则静默排除宿主版本、安装时报 `ERESOLVE` 的问题。

## 1.1.1 (2026-08-31)

### Fixes

- 修复身份解析在 Windows 等只安装部分 Trae 版本（如仅 SOLO）的机器上读取不存在的存储文件而抛 `ENOENT`、导致刷新与聊天请求全部失败的问题：现在按「第一个实际存在的 CN/SOLO 存储候选」解析 Trae identity，与凭据存储的跳过缺失语义保持一致。

## 1.1.0 (2026-08-30)

### Fixes

- 保持 `llm_utils_chat` / `solo_work_lite` 为模型调用主路径，继续保留 Trae 原生结构化 `tool_calls`，避免模型无法调用 DSH 本地 `read` / `write` / `bash` 工具。
- 删除只提取最终文本、无法返回 DSH `tool_calls` 的 `TraeSoloRemoteBridge` 及 Remote 会话调用逻辑；保留独立、只读的 `TraeSoloRemoteCatalogClient` 用于刷新完整模型能力目录，类型上不提供聊天方法，防止再次误接为模型调用主路径。
- 收紧 SOLO 请求为实证字段 allowlist，过滤会触发 `param is invalid` 的 OpenAI 可选字段；推理档位完成 DSH canonical → Trae wire 转换。
- 修复 `get_detail_param` 解析器字段名：上下文窗口改读 `model_detail_list[].prompt_max_tokens`（回退 `context_window_tokens.dev`）、最大输出改读 `model_detail_list[].max_tokens`。原代码读不存在的 `max_input_tokens` / `max_output_tokens`，导致每个模型的 contextWindow / maxTokens 恒为 undefined。
- 模型发现合并时剔除「Remote 目录有、但 `get_detail_param` 无对应 `config_name`」的不可调用模型（`Doubao-Seed-Code`、`glm-5.3` 均属此类，发往 `llm_utils_chat` 必返回 `4001 param is invalid`）；`FALLBACK_TRAE_MODELS` 移除已下线的 `Doubao-Seed-Code`。
- 账号选择改为严格绑定用户显式选择：删除启动时按通用积分自动挑选账号的逻辑，未选号时仅用第一个发现的账号；账号失效时不再静默切换到其他账号，而是报「未登录」让用户重新选择，避免账单落到用户未选择的账号上。

### Changes

- 模型管理体验与 `dsh-connect-workbuddy` 对齐：一个上游模型只对应一个 DSH 模型 id，移除运行时 `@1m` 变体，改用逐模型 `contextBudgets` 在 Trae 公布的默认 / Max 窗口之间选择。
- 未勾选任何模型时按完整目录提供模型，避免初次配置或旧设置迁移后 provider 目录为空；旧配置中的 `@1m` 行会被自动过滤。
- 模型卡片改为右侧上下文预算单选或固定窗口值，并统一显示多模态标记与原始推理档位 `low / high / xhigh`。
- 模型发现草稿补充与适配器目录一致的 `inputModalities`；当前 DSH 版本可能在核心规范化阶段丢弃该扩展字段，但正式 PiAiAdapter 模型元数据与图片请求链路保持完整。
- Trae SOLO 请求改为按已验证字段构造 `llm_utils_chat` envelope，过滤 OpenAI 可选参数以避免 `param is invalid`；同时将 DSH 推理档位映射为模型声明的 Trae wire value，并继续规范化 `developer` 为 `system`。
- 模型发现以 Remote `/models` 目录为骨架，用 `get_detail_param` 补充 `wireConfigName`（`llm_utils_chat` 真正接受的 `config_name`），按 `config_name == id` 优先、`display_name == name` 次之两级 join；join 不到 wire 行的 remote 模型（不可调用）会被剔除，修复 Seed-Code 等模型因展示名与 wire id 不一致导致的 `param is invalid`。

### Docs

- 更新 README 顶部插件卡片截图（账号选择、积分卡片与模型列表的当前界面）。
- 移除仓库内开发期的一次性探测脚本（`scripts/probe-*.mjs`、`scripts/inspect-raw-chat-log.mjs`）及其只读脚本内容断言测试，保持仓库与发布包聚焦产品代码；`lib/`、`tests/` 与 `node_modules/` 依旧不进入发布包。

## 1.0.1 (2026-08-31)

### Changes

- 将 Cordis 插件运行 ID 从 `llm-trae` 统一调整为 `dsh-connect-trae`，与 npm 包名保持一致。已有 1.0.0 本地安装升级后如保留旧配置条目，需移除旧的 `llm-trae` 实例，避免重复加载。

### Windows support

- `src/identity.ts` 现按平台读取 `product.json`：macOS 保持原路径，新增 Windows 路径 `<LOCALAPPDATA>\Programs\<AppName>\resources\app\product.json`（缺失时回退 `<home>\AppData\Local`），Windows 上 `appVersion` 不再恒为 `undefined`，会随请求头发送 `x-app-version` / `x-ide-version`。
- `src/identity.ts` 的 `osVersion` 在 Windows 上由 `win32 <release>` 规范化为 `Windows <release>`。
- `src/identity.ts` / `src/model-cache.ts` 路径推导参数化（`platform` / `home` / `env` 可选注入，默认取真实环境），便于跨平台测试；所有平台判断统一使用同一平台源，避免 `x-device-type` 与 `x-os-version` 自相矛盾。
- `src/model-cache.ts` 的 `state.vscdb` 路径按平台推导；该模块依赖 `sqlite3` 命令行，Windows 默认未安装，Raw Chat 探测会失败并安全回退（Raw Chat 默认关闭，不影响主流程），详见 README「Windows 说明」。
- 新增 Windows / Linux / `sg` / `solo-sg` 的 identity 测试用例；修复 `tests/identity.spec.ts` 中依赖测试机平台类型的断言（现显式注入平台，Windows 真机与 CI 均可通过）。

## 1.0.0 (2026-08-30)

### Features

- 首个稳定版本：将本机当前登录的 Trae 中国区模型接入 DSH，并通过安全 loopback shim 提供模型调用。
- 接入 `llm_utils_chat` 原生函数调用通道，将 Trae `function_call` 转换为 DSH 可执行的 OpenAI `tool_calls`，支持工具结果回传与连续 Agent 循环。
- 自动发现 Trae CN / TRAE SOLO CN 本地登录账号，支持刷新 Token 列表、选择账号，并优先使用具有通用积分的账号。
- 提供 DSH Connect Trae 插件卡片，分别展示 Work 积分与 DSH 可使用的通用积分，并支持模型目录刷新和启用选择。
- 支持 DeepSeek-V4-Flash 等 Trae 模型、只读用量接口及中英文界面。

### Fixes

- 凭据选择优先使用可供 `llm_utils_chat` 计费的通用积分账号；单个损坏、过期或已退出的本地凭据不会阻断其他账号。
- 规范化 DSH 的 `developer` 消息角色为 Trae 接受的 `system`，避免模型请求持续 400 重试。
- 正确处理 Trae 流式错误事件，配额错误不再被误报为 `EMPTY_RESPONSE`。

### Docs

- 发布元数据、双语 README、发布流程、第三方 Trae 相关项目声明与 npm 打包白名单均已补齐。
- 项目以 MIT 许可证发布，版权归属明确为 `Copyright (c) 2026 LaoDing`。

## 0.1.0-dev.1 (2026-08-28)

### Features

- **新版 SOLO 远程会话通道**：`TraeSoloRemoteClient` + `TraeSoloRemoteBridge`，把 `solo.trae.cn/api/remote/v1/chat_sessions` 的轮询结果转换为 OpenAI SSE，接入安全 loopback shim，成为第一可用上游路线。
- **本地模型目录**：`DeepSeek-V4-Flash` / `DeepSeek-V4-Pro` / `Doubao_1_6` / `kimi-k2.6` / `qwen-3.6-plus` / `glm-5.1` / `minimax-m2.7`。
- **只读用量概览**：`TraeUsageClient` 查询总可用额度、积分来源、每日签到与奖励活动（`web_user_ent_usage` / `checkin_credits/status` / `activity/info`），只读、不消耗积分。
- **插件设置卡片**（对齐 `dsh-subagent-default-model` 外部形象）：在 `settings.plugin.item` 注册折叠卡片（key `trae`），带 LD 品牌图标与 `dsm-plugin-card` 卡片外壳，展开后展示总可用/已消耗、各项积分进度条、每日签到与奖励活动；Host 侧通过 `webServer` 只读路由 `/plugins/dsh-connect-trae/usage` 提供脱敏数据。
- **SSE 扩展**：解析 `token_usage` 与 `tool_calls` 事件。
- **安全骨架**：随机 loopback 端口、进程内随机 secret、Host/Origin/Content-Type 校验、请求取消、body 上限。

### Docs

- 新增 `docs/SOLO_ROUTE_DECISION.md`、`docs/USAGE_API_RESEARCH.md`、`docs/HANDOFF.md`。
- README 中英双语双文件，对齐插件外部形象标准。
- 新增 `THIRD_PARTY_NOTICES.md` 第三方开源声明：只记录与 Trae 接入直接相关的架构/协议参考项目及其许可证与合规说明；README 增加对应章节，发布包 `files` 白名单纳入该文件。
