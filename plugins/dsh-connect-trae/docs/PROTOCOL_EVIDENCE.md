# Trae CN 协议证据矩阵

> 本文只记录脱敏结构、字段名、长度和行为。不得复制 token、用户消息正文、账号信息或完整请求 body。

## 证据等级

- **A：历史真实请求日志**——本机 Trae 曾实际发出并成功返回。
- **B：当前安装包可执行文件/bundle**——可证明客户端具备某字段或分支，但未必是当前请求必填。
- **C：失败参考实现**——只能作为待验证假设。
- **D：本项目草案**——纯离线结构，不能证明上游接受。

## Endpoint

| 结论 | 等级 | 证据 |
|---|---|---|
| CN 主聊天使用 `/api/agent/v3/create_agent_task` | A | ai-agent 历史日志：chat RPC 后 HTTP 200、SSE first-token |
| `/api/agent/v3/llm_utils_chat` 用于标题、图标、分支名、commit message 等轻量任务 | A+B | 历史日志的 `generate_session_title_and_icon`；dylib 错误字符串 |
| `/api/cue_agent/v3/create_agent_task` 属于 CUE/补全 agent | B | `cueMain.js` endpoint、事件枚举及 commit_toolcall_result |
| 三个 endpoint 可共用一个 body | 否定 | A+B | 语义、事件和调用链不同 |

## Headers

| Header | 当前证据 | 状态 |
|---|---|---|
| `Authorization: Cloud-IDE-JWT ...` | 参考实现 + 安装包请求代码 | 高可信，仍需受控请求确认 |
| `X-Cloudide-Token` | 参考实现 | 待确认 |
| `x-app-id` | A，历史日志 | 已确认存在 |
| `x-machine-id` | A；值形态对应64字符 `telemetry.machineId` | 已确认来源 |
| `x-device-id` | A；值等于唯一 `iCubeAuthInfo://icube-dc:<id>` 键后缀 | 已确认来源 |
| `x-device-type` | A，当前为 `mac` | 已确认 |
| device brand/cpu/os version | A | 已确认存在，是否必填未知 |
| IDE version/type/code | A | 已确认存在，动态来源需完善 |
| `X-Request-ID` / `X-Trae-Request-ID` | A | 同一 UUID |
| traffic/trace headers | A | 存在，最小必填性未知 |

## Body

### 已确认的上下文组成

历史日志在请求前已持有：

- session/task/message/trace IDs
- local/cloud agent type
- function
- config/model name
- memory 开关
- enabled skills
- 历史、文件、工具及其它渲染上下文

一次成功请求 body 长度约146KB，说明完整 agent task 不是简单的 OpenAI messages wrapper。

### 二进制结构字符串

`libai_agent.dylib` 暴露以下序列化结构名/字段名线索：

- `struct Request with 8 elements`
- `ClientInfo`（41 elements）
- `Context`
- `History`
- `Message`
- `ChatAssistantTaskContent`
- `client_info`
- `client_config_ab_versions`
- `messages`
- `model`
- `function`
- `session_id`
- `trae_request_type`
- `request_traffic_type`
- filesystem、workspace、selected code、terminal、documents、file changes、skills、tools、memory 等大量上下文字段

安装包还包含日志格式字符串 `[create_agent_task] request body:`，但当前默认日志级别下未记录实际 body；不能为了取证去提高日志级别并触发真实请求，除非用户明确同意。

### 当前结论

`src/protocol.ts` 的简化 body 仅为 D 级草案。它不能进入真实 upstream client，直到最小必填结构被 A/B 级证据支持。

## SSE

| 事件/行为 | 等级 | 说明 |
|---|---|---|
| `progress_notice` | A | 5份日志中7829次原始 unknown-event 记录 |
| history events | A | 解析后日志，原始 wire event 名未知 |
| timing event | A | payload 有 first-token/queue/server timing |
| thought/reasoning | A | agent解析层记录首 token；原始 payload 名待确认 |
| token usage | A+B | agent日志与二进制均有处理分支 |
| tool calls | A+B | agent内部大量处理；CUE bundle有明确事件名，但主聊天wire名待确认 |
| turn completion / done | B | dylib处理分支明确存在 |

当前 `SseDecoder` 可以无损保留未知事件，并显式识别 `progress_notice`；尚不能把主聊天所有事件转换成 OpenAI delta。

## Raw Chat 协议族

二进制证据显示 Trae 内部还提供：

- `api/ide/v2/llm_raw_chat`
- `api/ide/v1/llm_raw_chat`
- `api/ide/v1/llm_raw_chat_prompt`

并包含 `LLMRawChatMessage`、multi-content、tool call/function call、reasoning、finish reason、usage 和 `[DONE]` 等结构。这比完整 Agent Task 更匹配 DSH Provider 的职责边界。

历史 Agent timing 的 `name=llm_raw_chat_v2` 也说明主 Agent 内部最终调用 raw-chat 模型阶段。基于这些证据，首阶段实现策略已调整为优先恢复 v2 raw-chat，而不是复刻146KB的完整 Agent Task。决策详见 `docs/ARCHITECTURE_DECISION.md`。

二进制字符串证明协议存在，但尚未确认顶层body schema和额度授权方式。

### 受控v2探测结果（2026-08-28）

经用户明确同意，执行了一次且仅一次 `POST /api/ide/v2/llm_raw_chat` 短探测：

- 提示长度22字符，`max_tokens=8`，无工具。
- 使用已确认的64字符machine ID和15字符device ID。
- 没有v1、agent-task或title endpoint回退。
- 返回HTTP 400，响应体为空，未产生可解析错误结构或SSE事件。
- 输出仅包含header名称、body键名、长度和状态，不包含token、用户ID、提示正文或回复正文。

结论：当前OpenAI式顶层草案仍缺少Trae v2必填字段，不能接入正式upstream。由于服务没有返回缺失字段说明，本轮不继续试错，也不自动降级v1。

### 模型配置日志修正

历史 `model_info: CustomModel` 日志为预置 `glm-5.2` 明确给出：

- `config_name = "glm-5.2"`
- `model_name = "glm-5.2"`
- `raw_chat_function = None`
- `prompt_set = None`
- `ab_versions = None`
- `use_remote_service = true`

因此此前把 `prompt_set` 与 `ab_version` 设为非空必填是假设过度。实现已修正为只要求有证据的`config_name`，其余字段仅在Trae日志明确为`Some(...)`时发送。

同一日志显示模型配置先通过`/api/ide/v1/batch_get_detail_param`获取，函数列表包含`inline_chat`、`chat`、`chat_v3`、`solo_agent`等。Raw Chat所需动态配置可能来自该响应，而不是本地静态文件；当前历史日志只记录response headers，没有记录response body。

### 思考强度（Reasoning Effort）

Trae客户端明确具备模型级思考强度能力，动态库包含：

- `reasoning_effort_options`
- `default_reasoning_effort`
- `reasoning_effort`
- 五个值：`minimal`、`low`、`medium`、`high`、`xhigh`

历史 `CustomModel` 日志中的132条样本当前全部为 `reasoning_effort: None`，包括预置`glm-5.2`。这表示当前日志没有证明GLM-5.2在该版本实际开放可选强度，不能仅凭二进制字符串为所有模型宣告五档支持。

新增 `src/reasoning.ts`：只有模型元数据明确返回`reasoning_effort_options`时才公布和发送对应值；默认值必须属于支持列表；未声明能力时拒绝强行设置。这与用户要求的“拿到模型思考强度设置”兼容，同时避免像WorkBuddy一样完全忽略，也避免虚构模型能力。

模型详情接口`batch_get_detail_param`理论上是获取各模型`reasoning_effort_options/default_reasoning_effort`的权威来源，但当前受控探测仍返回HTTP 400空响应，尚未取得实际模型矩阵。

后续校验确认：历史成功请求的185字节body对应枚举的数值序列化（`mode_type=0`、`access_type=0`），当前探测已精确复刻该长度；同时补齐历史成功请求中的版本、设备、OS和trace headers。CN桌面access token已过期，但插件的单飞刷新成功产生有效DSH副本，重新探测仍为400。因此问题不是token过期、枚举大小写或已知通用headers，残余差异位于官方HTTP认证/租户封装或当前版本schema。

### DTO与响应字段证据

进一步静态分析定位到 `ai_agent::infrastructure::adapter::llm::dto`，其中明确列出：

- `LLMRawChatMessage`
- `LLMRawChatToolFunction`
- `LLMRawChatImageURL` / `VideoURL`
- `LLMRawFunctionCall`
- `LLMRawMultiContent`
- `LLMRawToolcallItem`
- `LLMRawExtraInfo`
- model/config/prompt/usage相关 DTO

同一动态库的provider解析器还明确包含 OpenAI式字段：`choices`、`delta`、`finish_reason`、`reasoning_content`、`tool_calls`、`prompt_tokens`、`completion_tokens`、`total_tokens`和`[DONE]`。

这使“Raw Chat使用OpenAI式message/tool/stream结构”从D级猜测提升为B级结构证据，但顶层字段的必填性、v2差异和Trae自有extra_info仍未确认。

### 本地数据库与日志检查

Trae CN 的 Agent 状态文件位于 `ModularData/ai-agent/database.db`，当前约1.4GB；文件头不是SQLite，`sqlite3`明确返回“file is not a database”。这与动态库中的加密/存储实现相符，不能把它当普通SQLite读取，也不应绕过Trae存储保护。

动态库存在 `[LLMAdapter] llm_raw_chat_custom_model request:` 调试格式，但当前历史日志没有匹配记录，说明默认日志级别/当前账号路径没有留下可安全复用的raw-chat body。

### 离线模型

新增 `src/raw-chat.ts`：

- 显式区分v1/v2 endpoint。
- 建模text/multimodal/tool messages和tool definitions。
- 构造纯离线OpenAI式body草案。
- 解码text、reasoning、tool-call、usage、finish reason和`[DONE]`。
- 未知payload无损保留。

该模块不执行fetch，不能被视为上游已可用。

### Raw Chat 主链路 / SOLO 回退安全边界

新增 `TraeFallbackUpstreamClient`，为未来 Raw Chat 切主链路预先固定非幂等安全规则：

- 仅在主链路明确返回 HTTP 400 / 404 / 415 且尚未得到 Response，或明确为 `unconfigured` 时回退；
- 401 / 403、额度不足、429、服务端/网络错误不回退，避免隐藏账号和计费错误；
- 主链路一旦返回 Response，即使 SSE body 后续失败也不回退，避免同一请求双重计费或重复工具调用；
- AbortSignal 已取消时不回退；
- 回退只通过可选脱敏回调记录错误分类，不记录请求、token 或生成内容。

该组合器已有离线测试，但在 Raw Chat live probe 成功前不会挂入生产链路。

### 当前 Trae 3.3.83 平台限制（2026-08-29）

已用当前有效凭据、当前设备身份、精确 513-byte model-detail body、官方 16/20-header 集分别通过 Node fetch 与系统 curl 探测。两者均返回 HTTP 400 空响应；同一请求经 Trae native AhaNet 返回 HTTP 200。已排除普通 Cookie、代理路由、JSON 字节、header 大小写和 curl/Undici 实现差异。

AhaNet 位于 Electron NativeExtensionService / `libai_agent.dylib` 私有 ABI 中，JS 层没有公开 fetch bridge；内部 Unix socket/RPC 会话由 Trae 主进程建立。插件不会直接加载私有 dylib、连接内部 socket、安装 TLS MITM 证书或复用第三方自定义模型密钥。由此，当前版本的预置模型 Raw Chat gateway 不能由独立 DSH 插件安全复现。

已实现 capability-gated Raw Chat 框架：默认完全禁用；只有显式启用且短探测成功才成为 primary；否则稳定使用 SOLO Remote。该限制不是完成 text/reasoning/tool_calls/usage/done live 验证的替代，目标仍需等待公开 contract 或可验证的 native request sample。

## 发布/联网门槛

启用真实 upstream 前，至少满足：

1. 首选 raw-chat endpoint：v2已单次实测，但当前草案返回400。
2. machine/device ID：已满足。
3. raw-chat最小body schema：OpenAI式核心字段有B级证据，但Trae必填extra/config字段未满足，是当前阻断项。
4. raw-chat text/reasoning/tool/done payload：OpenAI式字段有B级证据，wire格式未满足。
5. 离线fixtures：基础SSE及Raw Chat chunk已满足，真实事件未满足。
6. 用户批准的单次短探测：已完成；在获得更多body证据前不继续试错。
