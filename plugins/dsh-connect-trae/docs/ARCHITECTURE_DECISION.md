# 架构决策：优先研究 `llm_raw_chat`，不直接复刻完整 Agent Task

## 状态

Superseded as first implementation route by `docs/SOLO_ROUTE_DECISION.md`。Raw Chat结论保留作研究和未来路线。

## 背景

历史日志确认 `/api/agent/v3/create_agent_task` 是 Trae 主 Agent 链路，但其请求包含完整 Agent 上下文、工具、skills、workspace、memory 和多层 ID，一次 body 可达约146KB。直接复刻该协议会把 DSH 的 agent/tool 体系与 Trae 自身 agent runtime 双重叠加，复杂度和语义冲突都很高。

## 新证据

当前 `libai_agent.dylib` 同时包含更接近标准模型调用的协议族：

- `api/ide/v1/llm_raw_chat`
- `api/ide/v2/llm_raw_chat`
- `api/ide/v1/llm_raw_chat_prompt`
- `LLMRawChatMessage`
- `LLMRawMultiContent`
- `LLMRawToolcallItem`
- `LLMRawFunctionCall`
- `LLMRawExtraInfo`
- `LLMRawChatImageURL` / `LLMRawChatVideoURL`
- `reasoning_content`
- `finish_reason`
- `tool_calls`
- `token_usage`
- `[DONE]`

另外，历史主 Agent timing 中 `name = llm_raw_chat_v2`，表明 `create_agent_task` 的内部模型阶段最终也落到 raw-chat 语义。

## 决策

后续协议研究顺序调整为：

1. 优先恢复 `api/ide/v2/llm_raw_chat` 的最小请求/响应 schema。
2. 如果 v2 缺少证据，再研究 v1；不把两者作为盲目回退。
3. `create_agent_task` 保留为“Trae完整Agent模式”的未来选项，不作为第一阶段 DSH LLM Provider 的首选。
4. `llm_utils_chat` 继续只用于标题、图标、branch name 等工具任务，不作为主聊天。
5. DSH 继续拥有会话编排、工具调用和权限；Trae raw-chat 只提供模型推理。

## 理由

- 避免双 Agent runtime。
- 与 WorkBuddy 的“DSH掌控工具/会话，上游只做模型流”架构一致。
- raw-chat 二进制结构已经显示 OpenAI式 message/tool/reasoning/usage 字段，更适合 PiAiAdapter。
- 可以用小型离线 fixture 和一次极短 live probe 验证，而无需构造146KB Agent上下文。

## 已进一步确认

- DTO层存在message、multi-content、function/tool call和extra info结构。
- provider层存在OpenAI式choices/delta/reasoning_content/tool_calls/finish_reason/usage和`[DONE]`。
- 已建立纯离线Raw Chat请求/响应模型与测试，但没有执行网络。

## 仍需确认

- v2 raw-chat body 的顶层必填字段和认证 Header。
- model/config/function/extra_info的准确映射。
- SSE 事件是否是 `data:` OpenAI chunk、命名事件或两者混合。
- Trae订阅额度是否允许直接调用 raw-chat endpoint。
- CN/solo与SG是否使用相同版本。

## 否决方案

- 三个 endpoint 使用同一个 body 自动回退。
- 首阶段复刻完整 `create_agent_task`。
- 使用 `llm_utils_chat` 承担主聊天。
- 在没有 schema 证据时直接发送真实请求。
