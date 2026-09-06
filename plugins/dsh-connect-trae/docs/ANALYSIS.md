# WorkBuddy 与 Trae 接入分析日志

> 本文是持续更新的研究记录。结论分为“代码已证实”和“待现场验证”，避免把推测写成事实。

## 1. 当前范围与版本

| 项目 | 用途 | 分支/版本 |
|---|---|---|
| `dsh-connect-trae` | 最终实现项目 | `main`，当前仅有基础文档 |
| `dsh-workbuddy-connect` | 已验证可用的 DSH Provider 参考 | `main` / `d91d804` / npm `0.2.3` |
| `dsh-trae-api` | Trae 协议资料及失败样本 | `master` / `080dcf8` / npm `1.0.2` |

## 2. 第一轮关键结论

### 2.1 两个项目的产品定位实际上不同

**代码已证实：**

- WorkBuddy 项目直接注册为 DSH LLM provider。`src/index.ts` 等待本地 shim 就绪后，通过 `ctx.llm.registerAdapter()` 注册 adapter，并通过 `registerConfigurableProviders()` 加入 provider 目录。
- Trae API 项目只把 Express 兼容代理作为 Cordis 插件启动。`lib/index.js` 仅调用 `startServer()`，没有注入 `llm`、没有注册 DSH adapter，也没有把模型加入 DSH 模型目录。

因此，“插件成功启动一个 9220 端口”不等于“Trae 模型成功接入 DSH”。这是当前最明确的架构差异，也很可能是原 Trae 项目在目标场景中失败的首要原因。

### 2.2 WorkBuddy 的成功链路

已确认的主链路：

```text
Cordis 加载插件
  -> apply(ctx, config)
  -> 创建 CredentialStore / Catalog / UpstreamClient
  -> 启动仅监听 127.0.0.1 随机端口的 OpenAI shim
  -> shim.ready 后创建 PiAiAdapter
  -> ctx.llm.registerAdapter(['workbuddy'], adapter)
  -> DSH 模型调用 PiAi/OpenAI chat completions
  -> 本地 shim 校验进程内随机 bearer
  -> CredentialStore 每次按需解析/刷新真实凭据
  -> WorkBuddy upstream SSE
  -> shim 原样回传给 DSH/pi-ai
```

关键文件：

- `dsh-workbuddy-connect/src/index.ts`：插件装配、生命周期、provider 注册、动态目录刷新。
- `dsh-workbuddy-connect/src/adapter.ts`：使用 `PiAiAdapter` 和 `openAICompletionsApi()` 接入 DSH LLM seam。
- `dsh-workbuddy-connect/src/shim.ts`：将上游私有差异隔离为本地 OpenAI-compatible endpoint。
- `dsh-workbuddy-connect/src/upstream.ts`：上游协议、强制流式、header、错误分类、模型和额度接口。
- `dsh-workbuddy-connect/src/auth.ts`：桌面凭据只读、DSH 自有刷新副本、原子写入、单飞刷新。

### 2.3 WorkBuddy 值得迁移的设计

1. **直接注册 DSH provider**：不是要求用户手动配置一个本地 OpenAI Base URL。
2. **shim 隔离私有协议**：DSH/pi-ai 只面对稳定的 OpenAI completions；Trae 差异留在 shim/upstream 层。
3. **随机端口和进程内 secret**：避免固定端口冲突，也避免任何本地进程直接盗用账号额度。
4. **真实凭据不进入 pi-ai**：adapter 只向 shim 发送共享 secret；shim 再从 store 获取上游 token。
5. **桌面文件只读**：刷新结果写进 DSH 自己的 0600 文件，不污染宿主应用文件。
6. **凭据按请求解析、临期单飞刷新**：账号切换和 token 更新可以自然跟随。
7. **静态模型兜底 + 动态模型目录**：上游目录失败时 provider 不会消失。
8. **生命周期完整**：shim、adapter、directory、heartbeat 均有 disposer。
9. **错误分类明确**：额度不足、限流、会话失效、上游故障映射成不同 HTTP 状态。
10. **测试覆盖架构边界**：auth、shim、安全加固、upstream、设置集成和 live E2E 都有独立验证入口。

## 3. dsh-trae-api 已确认的问题与风险

### 3.1 DSH 集成缺失（高优先级、已证实）

- `lib/index.js` 没有 `inject = ['llm']`。
- 没有 `ctx.llm.registerAdapter()`。
- 没有 configurable provider 注册。
- `cordis.patch.yml` 只挂载服务器插件。

结果：即使代理成功运行，DSH 模型选择器也不会自动获得 Trae provider。

### 3.2 模块系统边界已显式处理，但运行依赖必须安装（已证实）

根 `package.json` 声明 `"type": "module"`，`lib/index.js` 是 ESM；`src/package.json` 明确声明 `"type": "commonjs"`，所以 `createRequire()` 加载 `src/server-core.js` 的方式在模块边界上成立，不应再把它列为 ESM/CJS 冲突。

实际执行最小导入测试时失败于 `Cannot find module 'dotenv'`，原因是参考仓库尚未安装 `node_modules`，不是模块边界错误。这说明后续运行验证前必须先安装锁定依赖，同时也暴露出该仓库没有零依赖静态验证入口。

### 3.3 插件启动生命周期不可靠（已证实）

- `startServer()` 在 `app.listen()` 真正成功前立即返回。
- `lib/index.js` 随即记录“listening”日志，即便之后发生 `EADDRINUSE`。
- 固定默认端口 `9220`，同一机器多 profile 或残留进程容易冲突。
- `options.port || process.env.PORT || '9220'` 还会把合法的 `port: 0` 当作假值并退回 9220。实际用 `apply(ctx,{port:0, manualToken:'test-token'})` 冒烟测试，服务仍监听 `127.0.0.1:9220`，日志也宣称 9220。
- disposer 只调用 `server.close()`，未处理开放连接，也没有等待关闭。
- 认证初始化失败仍继续监听，仅将 `authOk` 标为 false。

### 3.4 凭据处理弱于成功参考（高风险、已证实）

- 会将 access token、refresh token 等以明文写入仓库目录下 `.env`。
- `_logAuth()` 会输出 token 前 40 个字符。
- 使用同步文件 I/O，缺少文件锁、原子写和严格权限设置。
- 读取桌面 `storage.json` 后把凭据复制为长期状态，不能像 WorkBuddy store 那样自然选择桌面端和插件端最新凭据。
- 刷新互斥是布尔值：并发请求遇到刷新时，后续调用直接返回而不是等待同一个刷新 Promise。
- 刷新失败只记录日志，调用方随后可能继续使用过期 token。

### 3.5 Trae 请求身份不稳定（待现场验证，但代码风险明确）

`src/trae-client.js` 每次请求都会随机生成新的 machine ID，再派生 device ID，同时硬编码 Windows、IDE 版本和版本码。若上游校验设备绑定、平台一致性或版本有效性，这会造成认证拒绝或风控。正确做法应优先读取 Trae 已持久化的真实设备标识，至少也应生成一次后稳定保存，而不是每次请求变化。

### 3.6 “三级端点回退”可能掩盖协议不兼容（待现场验证）

三个端点被发送完全相同的 body：

- `/api/agent/v3/llm_utils_chat`
- `/api/ide/v1/chat`
- `/api/agent/v3/create_agent_task`

不同语义端点通常需要不同请求结构和响应解析。当前实现没有 endpoint-specific adapter，因此所谓回退可能只是连续发送三个不兼容请求，并增加额度或风控风险。

### 3.7 工具调用依赖提示词模拟，不是 Trae 原生结构化协议（高优先级、已证实）

- `toolsToSystemPrompt()` 把工具定义转成 `<tool_call>` 输出约定。
- 历史 `tool_use/tool_result` 被扁平化成普通文本。
- OpenAI 和 Responses 输入转换同样把 function call 变成文本。
- `anthropic-format.js` 确实实现了非流式正则解析和 `StreamingToolCallParser`，会把模型生成的 `<tool_call>{JSON}</tool_call>` 转回 Anthropic `tool_use` 块。
- 但 OpenAI `openai-format.js` 只产生 `delta.content`，没有 `tool_calls` 增量；Responses 输出也只处理文本。

所以 Claude Code 的 Anthropic 路线存在“提示词模拟工具调用”的实现，但它依赖模型严格遵循 XML/JSON 格式，不具备上游原生 tool-call 的约束和可靠性；OpenAI/Responses 路线则没有结构化工具输出。README 的“完整支持”缺少端到端测试证据。

### 3.8 消息清洗可能破坏 DSH/Agent 语义（已证实）

`cleanContent()` 使用宽泛正则删除 system-reminder、command 元信息、available tools 等内容。这可能删除 Harness/Claude Code 的安全约束、任务上下文或工具说明。目标 DSH provider 不应擅自清理宿主生成的系统内容，除非有可重复测试证明某个字段上游不接受。

### 3.9 模型目录并非上游发现（已证实）

`getModels()` 忽略 `baseUrl`，只是返回硬编码 `MODEL_TIERS`。模型映射也包含未来或私有名称，并把多个 Claude/GPT 名称映射至固定 Trae 模型。模型是否真实可用、上下文和输出上限均未验证。

### 3.10 本地代理鉴权不足（高风险、已证实）

- 默认 API key 是公开固定字符串 `trae-local-api`，对任何本机进程几乎不构成秘密。
- 支持 `API_KEY=none` 完全关闭鉴权。
- CORS 对 loopback origin 放行且使用 `Access-Control-Allow-Headers: *`，没有 WorkBuddy shim 的 Host、Origin、Content-Type、进程内随机 bearer 四重边界。
- 新实现应使用每进程随机 secret，只让内部 adapter 知道；若保留对外 API，则必须作为独立、显式开启的功能设计。

### 3.11 流式取消和网络边界缺失（高风险、已证实）

- 上游 `fetch()` 没有超时，也没有接收 AbortSignal。
- OpenAI/Anthropic 响应处理器直接读取 `fetchResp.body.getReader()`；客户端断开时不会 abort 上游请求。
- 这可能遗留连接、继续生成并消耗额度。
- 对 429 也没有解析 `Retry-After` 或明确重试策略。

### 3.12 缺少工程验证（已证实）

- 没有 test/typecheck/build/check 脚本。
- 仓库没有测试目录。
- `lib/index.js` 是手写入口而非可复现构建产物。
- README 声明的多协议、多版本、工具调用和端点回退没有自动化证据。
- 安装锁定依赖后，`node -e "import('./lib/index.js')"` 已通过，说明插件入口至少可加载；`trae-client.js` 的模型映射模块也可加载。
- `npm audit` 报告 1 个 moderate 级直接依赖问题：`uuid < 11.1.1`，对应 GHSA-w5hq-g745-h8pq。当前使用 UUID v4 路径未必能触发该公告涉及的 buffer 问题，但新实现不应继承已知脆弱版本。

## 4. 初步目标架构

建议以 WorkBuddy 的结构重建，而不是继续扩展当前大型 Express 转换器：

```text
src/index.ts
  装配 TraeCredentialStore / TraeCatalog / TraeUpstreamClient / TraeShim
  等 shim ready
  注册 provider=trae 的 PiAiAdapter 和设置目录

src/auth.ts
  只读发现各 Trae edition 的 storage.json
  解密并规范化凭据
  DSH_HOME 下保存插件自有刷新副本（原子、锁、0600）
  稳定设备身份

src/upstream.ts
  逐 edition 定义 endpoint、headers、request body、SSE decoder
  禁止一个 body 盲试不同语义端点
  对错误做可诊断分类

src/shim.ts
  127.0.0.1:0 + per-process secret
  暴露 pi-ai 真正需要的最小 OpenAI endpoint
  处理 abort、SSE 和 Trae 的协议差异

src/adapter.ts
  PiAiAdapter + openAICompletionsApi
  provider/models 注册到 DSH

src/catalog.ts
  已验证的静态兜底目录
  有真实接口时再动态刷新
```

## 5. 本机脱敏验证结果

### 5.1 WorkBuddy 参考实现验证

在参考仓库安装依赖后完成以下验证：

- `pnpm test`：8 个测试文件、60 个测试全部通过。
- `pnpm run typecheck`：Host 与 client 两套 TypeScript 配置均通过。
- `node scripts/verify-shim-hardening.mjs`：6 项安全断言全部通过，覆盖恶意 Host、恶意 Origin、非 JSON 请求、正常 loopback、缺失 bearer、错误 bearer。
- `pnpm install --frozen-lockfile` 本身因 pnpm 的 ignored-builds 安全策略以退出码 1 结束，涉及 `@google/genai` 和 `protobufjs` 构建脚本；但依赖实际已经可用，后续测试和类型检查均成功。没有擅自批准依赖构建脚本。

这些结果证明 WorkBuddy 不只是结构上合理，其核心适配、认证、shim、安全边界和 Cordis 设置集成确实有自动化验证支撑。真实账号 live E2E 尚未在本轮执行，以避免未经确认消耗额度。

### 5.2 Trae 本机认证文件验证

在当前 macOS 主机上，以下四个路径都存在 `storage.json`：

- `~/Library/Application Support/Trae CN/User/globalStorage/storage.json`
- `~/Library/Application Support/Trae/User/globalStorage/storage.json`
- `~/Library/Application Support/TRAE SOLO CN/User/globalStorage/storage.json`
- `~/Library/Application Support/TRAE SOLO/User/globalStorage/storage.json`

脱敏检查确认：

- 四个文件都包含 `iCubeAuthInfo://icube.cloudide`。
- 四个值当前均不是明文 JSON，而是编码/加密字符串。
- 使用现有 `decryptAuthData()` 对四个文件均可成功解密。
- 解密后的顶层字段结构一致：`token`、`refreshToken`、`expiredAt`、`refreshExpiredAt`、`tokenReleaseAt`、`userId`、`host`、`userRegion`、`account`。
- 研究过程中没有把 token、refresh token、用户 ID 或账号内容写入文档；仅记录字段名和类型。

这推翻了 README 表格中“SG 版为明文 JSON”可以普遍成立的假设：至少本机当前的 `Trae` 与 `TRAE SOLO` 文件也走可被 `tc` 解密器处理的编码格式。因此新实现必须**按内容检测格式**，不能只按 edition 决定明文或加密。

### 5.3 跨平台路径缺口

`dsh-trae-api/src/trae-decrypt.js` 的路径函数只按 Windows `%APPDATA%` 组织目录；在 macOS 上会退回 `$HOME/AppData/Roaming/...`，与本机真实路径不符。虽然直接把正确目录传给 `decryptAuthData()` 可以成功，但 `initAuth()` 自动发现逻辑在 macOS 上无法依靠现有默认路径正确工作。这是本机可重复确认的失败根因之一。

### 5.4 稳定设备身份取证

本机四套 Trae 数据目录都存在应用自有的 `machineid` 文件，且 `storage.json` 同时包含：

- `telemetry.machineId`
- `telemetry.devDeviceId`
- `telemetry.sqmId`
- `iCubeLastVersion`

脱敏比较确认：每个 edition 的 `machineid` 文件均为稳定的 36 字节标识；`telemetry.devDeviceId` 也是 36 字符。新实现已改为优先读取 Trae 自己持久化的 `machineid` 和 `telemetry.devDeviceId`，不再像失败样本那样每次请求随机生成身份；只有缺失 device ID 时才从稳定 machine ID 确定性派生。

安装包 `product.json` 还确认本机 Trae CN：

- `appVersion = 3.3.83`
- `tronBuildVersion = 2.3.62837`
- `buildPlatform = darwin`
- `buildArch = arm64`

因此失败样本硬编码 `Windows 10`、`x-device-type=windows`、旧 IDE version 的做法与当前本机事实不符。

### 5.5 安装包协议证据

对 `/Applications/Trae CN.app/Contents/Resources/app` 做只读搜索后确认，安装包中确实出现：

- `llm_utils_chat`
- `create_agent_task`
- `/api/ide/v1/chat`
- `x-machine-id`
- `x-device-id`

进一步读取 bundle 邻近代码与本机历史日志后，证据已经可以区分端点用途：

- `api/cue_agent/v3/create_agent_task` 属于代码补全/CUE agent，bundle 同时声明其事件包括 `task_created`、`thought`、`tool_call`、`chat_done`、`turn_completion`、`token_usage`、`progress_notice`，并配有 `commit_toolcall_result`；它不是普通 OpenAI chat completion 的透明替代。
- `/api/agent/v3/llm_utils_chat` 在历史 agent 日志中用于 `generate_session_title_and_icon`，即会话标题/图标等轻量 LLM 工具任务。
- `/api/agent/v3/create_agent_task` 才是 Trae 主聊天链路在历史日志中实际调用的 endpoint；日志明确记录 `service:"chat", method:"chat"` 之后构造 cloud agent task，并取得 HTTP 200 和 SSE first-token timing。

因此原失败项目把 `llm_utils_chat` 放在主聊天第一优先级、再把 `/api/ide/v1/chat` 和 `create_agent_task` 当作同构回退的策略没有协议依据。当前 CN 协议草案只把 `/api/agent/v3/create_agent_task` 视为未来受控探测候选，标题端点与 CUE agent 端点保持语义隔离。

### 5.6 离线 SSE 基线

新实现已加入通用增量 SSE decoder，覆盖：

- 任意 chunk 边界与 CRLF
- comment/keepalive
- 多行 `data:`
- 没有 `event:` 的 data-only SSE（原项目会静默丢弃）
- queue、output、reasoning、done、`[DONE]`
- 末尾没有空行的 flush
- 未知事件保留而不是静默吞掉

这只是兼容解析基线；真实 Trae 事件字段仍须由受控 live 取证确认。

### 5.7 历史日志提供的真实请求证据

在不发送任何新网络请求的前提下，脱敏读取本机已有 Trae CN 日志，得到以下已发生事实：

- 主聊天使用 `https://trae-api-cn.mchost.guru/api/agent/v3/create_agent_task`。
- 一次 `glm-5.2` 主聊天请求记录 HTTP 200、28 个 headers、body 长度约146KB；说明完整 agent task body 远比失败项目的简化 messages/model/body 复杂。
- 真实 headers 包含 app ID、IDE version/type/version-code、device brand/cpu/id/type、machine ID、OS version、traffic type、trace ID，以及同值的 `X-Request-ID`/`X-Trae-Request-ID`。
- 真实设备类型为 `mac`，真实 machine ID 形态是64字符 telemetry hash；另一个 `x-device-id` 是账号/设备体系中的短数字标识，而不是失败项目随机生成的 SHA 截断值。
- SSE 中确认出现 `progress_notice`；随后有 timing、thought/reasoning 与 first-token 记录。完整事件集合和 body 字段仍未在日志中完整暴露。

这也修正了上一轮身份理解：Trae 根目录 `machineid` 是稳定身份来源之一，但主聊天 header 日志显示 `x-machine-id` 实际对应64字符的 `telemetry.machineId`。脱敏关系比较确认根目录36字符 `machineid` 与 `telemetry.machineId` 不相等，其 SHA-256 也不等于 telemetry 值；CN 与 SOLO CN 则共享同一个 telemetry machine/dev 值。实现已改为优先使用 `telemetry.machineId`，根目录 `machineid` 仅作缺失时兜底。

`x-device-id` 的来源随后得到进一步确认：CN 与 SOLO CN 的 `storage.json` 都存在唯一的 `iCubeAuthInfo://icube-dc:221464824136636` 键，键后缀与历史官方聊天日志中的 `x-device-id` 完全一致。键值本身仍是加密字符串，未被输出或写入文档。实现现已优先使用唯一 `icube-dc:<id>` 后缀作为 device ID，`telemetry.devDeviceId` 仅作兜底。

构建产物脱敏验证当前 CN 映射为：64字符 machine ID、15字符 device ID、真实 build version、darwin 平台；与历史官方日志的形态一致。

### 5.8 离线 CN 请求草案

新增 `src/protocol.ts`，仅提供纯函数、不会发网络请求：

- 将主聊天 `/api/agent/v3/create_agent_task`、标题 `/api/agent/v3/llm_utils_chat` 分开建模。
- 构造简化 agent-task body 草案和 CN headers。
- 使用同一个 request ID 写入 `x-request-id` 与 `x-trae-request-id`。
- SG/solo-sg 会明确拒绝复用 CN 合约。

该草案用于固化当前证据和后续差异测试，不代表已经验证可用；真实 upstream 继续返回503。

### 5.9 历史 SSE 事件统计

只读扫描28份历史日志得到：

- `progress_notice` 作为无法识别的原始 SSE event，在5个 agent 日志中共出现7829次。
- agent 解析层大量记录 `History event received`、`TimingCostOriginEvent`、`token_usage` 和工具相关处理。
- 目前日志只会把未识别的 `progress_notice` 连同原始 event 名打印出来；已识别的 thought/tool/token events 通常进入内部结构后不再打印原始 event 名，因此不能根据字符串计数还原完整 SSE wire schema。

实现已经把 `progress_notice` 从 unknown 提升为显式 `progress` 事件，同时继续保留其他 unknown event，避免丢失未来取证信息。

### 5.10 agent-task body 复杂度判断

历史日志显示主聊天在发送前已经建立：

- session ID、task ID、message ID、trace ID
- local/cloud agent type
- function 与 config/model name
- memory 开关
- 已启用 skills
- 大量历史/上下文（实际 body 约146KB）

这说明失败项目的 `{messages, model, function, stream, request_id, session_id}` 只可能是一个未经验证的简化猜测。当前 `buildTraeAgentTaskBody()` 仅作为差异测试草案，不能视为最小可用 schema。

## 6. 下一步验证清单

1. 从 agent 二进制或日志级别配置中恢复 `/api/agent/v3/create_agent_task` body 的字段名集合，不记录消息内容。
2. 判断是否存在比完整 agent-task 更适合直接模型对话、且有明确请求 schema 的官方路径；不能重新把标题接口当主聊天。
3. 确认 Trae CN 与 SOLO CN 是否共享主聊天合约；SG 系列保持禁用直到有独立证据。
4. 继续恢复已识别的 thought/tool/token usage 等真实 SSE wire event 名和 payload shape。
5. 当前 endpoint 与 device/machine ID 已有强证据；仍需最小 body 和响应事件两项达到足够证据后，才向用户请求一次可能消耗额度的短文本探测确认。
