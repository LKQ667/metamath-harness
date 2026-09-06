# dsh-connect-trae 第一阶段实施方案

## 目标

先建立一个符合 DSH 扩展契约、安全边界清晰、可离线验证的 Trae Provider 骨架。第一阶段不承诺未经验证的多端点、多 edition 和完整工具调用，而是先打通最小可靠链路。

## 决策摘要

1. 采用 WorkBuddy 的 `DSH adapter -> loopback shim -> Trae upstream` 分层。
2. 当前项目直接注册 `trae` provider，而不是只启动固定端口代理。
3. shim 仅绑定 `127.0.0.1:0`，使用进程内随机 secret；真实 Trae token 不交给 pi-ai。
4. Trae 桌面认证文件只读；插件刷新副本写到 `DSH_HOME`，使用文件锁、原子写和 `0600`。
5. 按平台和 edition 探测候选路径，但按文件内容判断明文/加密格式。
6. 一个经过验证的 endpoint 对应一个明确的请求/响应 codec；禁止同一 body 盲试不同语义端点。
7. 先支持 DSH 实际需要的 OpenAI chat-completions seam；Anthropic 和 Responses 对外代理不属于首阶段必需范围。
8. 不使用宽泛正则删除宿主 system prompt、system-reminder 或工具说明。

## 模块拆分

```text
src/
├── index.ts             # Cordis 插件装配、设置、注册和清理
├── adapter.ts           # PiAiAdapter 与 trae provider
├── shim.ts              # 安全 loopback OpenAI endpoint
├── upstream.ts          # Trae endpoint、headers、请求体与错误分类
├── sse.ts               # 增量、安全的 Trae SSE 解析
├── auth.ts              # 凭据发现、解密、双源选择与单飞刷新
├── decrypt.ts           # tc/明文格式解析，不含路径策略
├── paths.ts             # macOS/Windows/Linux edition 候选路径
├── identity.ts          # 稳定设备身份解析/保存
├── catalog.ts           # 已验证模型兜底与动态刷新
├── host-heartbeat.ts    # Host 健康状态
├── bin.ts               # doctor/status，所有输出脱敏
└── client/              # 可选设置卡片，后置实现
```

## 阶段 A：工程与 DSH 骨架

交付：

- TypeScript、tsdown、Vitest 配置。
- `package.json` 的 DSH bundle/client 声明和 peer dependencies。
- `cordis.patch.yml` 注册 Host 插件但不修改默认模型。
- `index.ts` 声明 `inject=['llm']`，在 shim ready 后注册 adapter 和 configurable provider。
- 完整 disposer 与半注册失败回滚。

验收：

- `typecheck`、`test`、`build` 可重复执行。
- Cordis 集成测试能看到 `trae` provider、设置 namespace 和静态模型。

## 阶段 B：认证与平台发现

交付：

- macOS 四个已发现路径的支持，以及 Windows/Linux 候选路径策略。
- `storage.json` 只读解析。
- tc 与明文 JSON 内容检测。
- 解密结果 schema 校验；秘密永不进入日志和测试快照。
- `DSH_HOME/.trae-auth.json` 插件副本：锁、原子写、目录 0700、文件 0600。
- Promise 单飞刷新；验证 access 与 refresh expiry；刷新失败时只在旧 token 仍有效时降级。

验收：

- 用合成 fixture 覆盖格式、路径、损坏内容和并发刷新。
- 本机只运行脱敏 doctor，输出 edition、文件是否存在、到期状态，不输出 token/uid/account。

## 阶段 C：安全 shim 与 adapter

交付：

- `127.0.0.1:0` 随机端口。
- Host/Origin/Content-Type/per-process bearer 校验。
- `/healthz`、`/v1/models`、`/v1/chat/completions` 最小路由。
- request body 上限。
- 客户端断开时 abort 上游。
- stream idle timeout、上游超时和错误分类。

验收：

- DNS rebinding、跨站 Origin、非 JSON、无/错 bearer 测试。
- 上游中止、超时、额度、401、429、5xx 映射测试。

## 阶段 D：Trae 协议取证与离线 codec

在任何真实聊天探测之前：

1. 从 Trae 客户端或可重复证据确认真实稳定 device/machine identity 来源。
2. 确认当前 edition 的唯一首选 endpoint、headers 和 body schema。
3. 录制完全脱敏的 SSE 事件结构；不保存 token、用户信息和提示内容。
4. 用事件 fixture 建立离线解析测试：chunk 边界、多行 data、queue、output、done、无 done、reasoning、错误。
5. 若结构化工具调用未获证实，则明确标注首阶段不支持，不能用“完整支持”描述。

## 阶段 E：受控 live E2E

执行条件：

- 离线测试全部通过。
- 用户知情可能消耗 Trae 额度。
- 只调用一个已经确认的 endpoint。
- 使用极短提示并记录秘密脱敏后的状态、HTTP code、事件类型和耗时。

链路：

```text
adapter.stream
  -> pi-ai
  -> loopback shim
  -> Trae upstream
  -> SSE codec
  -> DSH text/usage chunks
```

验收：

- 模型出现在 DSH 模型目录。
- 能完成一次短文本流式回复。
- 取消请求会停止上游。
- 认证失败、额度不足和上游故障能给出不同诊断。

## 暂不纳入第一阶段

- 对公网或局域网开放代理。
- OpenAI Responses API 对外兼容服务器。
- Anthropic API 对外兼容服务器。
- 未经证实的三个 Trae endpoint 自动回退。
- 依赖模型遵循 `<tool_call>` 文本约定的“伪原生”工具支持。
- UI 卡片的复杂额度展示。

## 当前实施状态（2026-08-28）

阶段 A、阶段 B 和阶段 C 的安全骨架已完成：

- 已建立 TypeScript、Vitest、tsdown 和 pnpm 工程配置。
- 已创建 `trae` PiAiAdapter，并在 shim ready 后注册 DSH adapter、configurable provider 和 settings namespace。
- 已建立保守静态模型目录；其上下文参数仅作为骨架占位，真实协议验证后必须校准。
- 已实现 `127.0.0.1:0` 随机端口、进程内随机 bearer、Host/Origin/Content-Type 校验、JSON 校验、body 上限和连接关闭时 abort signal。
- 真实 Trae upstream 当前由 `UnconfiguredTraeUpstreamClient` 明确返回 HTTP 503，避免在协议尚未验证时误发请求。
- 已实现 macOS、Windows、Linux 的四 edition 路径候选，macOS 路径与本机实际安装一致。
- 已实现按内容识别明文 JSON 或 tc 加密、AES-CBC 解密和 SHA-512 完整性校验。
- 已实现只读桌面 `storage.json`、规范化凭据 schema、DSH 自有 0600 原子副本、最新凭据选择、Promise 单飞刷新和 refresh expiry 检查。
- CN/solo 刷新客户端已隔离实现；SG/solo-sg 因刷新契约未证实会明确拒绝，而不是套用 CN ClientID。
- 已确认主聊天 `x-machine-id` 对应64字符 `telemetry.machineId`，`x-device-id` 对应唯一 `iCubeAuthInfo://icube-dc:<id>` 键后缀；实现已按此读取，根 `machineid` 与 telemetry dev ID 仅作回退。
- 已实现增量 SSE decoder，覆盖 chunk 边界、CRLF、多行 data、data-only、queue/output/reasoning/done、无尾部空行和未知事件。
- 通过历史日志确认 CN 主聊天候选为 `/api/agent/v3/create_agent_task`，标题任务为 `/api/agent/v3/llm_utils_chat`，CUE agent 则是 `/api/cue_agent/v3/create_agent_task`；三者不再作为同构回退。
- 已实现不会发网的 CN 请求草案纯函数，并对 SG 系列设置合约拒绝。
- 已添加模型目录、路径、解密、凭据存储、稳定身份、SSE、Agent协议草案、Raw Chat离线模型、shim安全和真实Cordis/LLM provider注册测试。
- `pnpm run check` 已通过：TypeScript检查、10个测试文件共32个测试、tsdown构建全部成功。
- 使用构建产物对本机四套 Trae 文件做脱敏解析验证：四套均成功识别 access/refresh/host/expiry 的存在性；未输出任何秘密值。
- 使用构建产物脱敏验证 CN persisted identity：machine ID为64字符、device ID为15字符、平台为darwin，与历史官方请求形态一致。

尚未完成：

- 阶段 D 已确认设备身份和完整Agent endpoint；随后发现 `api/ide/v2/llm_raw_chat` 更符合DSH Provider职责，下一步转向恢复raw-chat最小body与text/reasoning/tool/done的真实SSE payload。证据与决策见 `docs/PROTOCOL_EVIDENCE.md`、`docs/ARCHITECTURE_DECISION.md`。
- 阶段 E 的受控 live E2E。

## 风险门槛

- 不把真实 token 写到仓库、`.env`、日志或开发文档。
- 不修改 Trae 桌面 `storage.json`。
- 不在未确认协议时对多个 endpoint 连续发送请求。
- 不在用户不知情时运行会消耗额度的 live E2E。
- 不以“服务启动”代替“Provider 已注册且端到端可用”的验收。
