# 架构决策：第一可用路线采用 Trae Work/SOLO通道

## 状态

Accepted，取代Raw Chat v2作为第一阶段首选上游。

## 综合参考

- `Sliverkiss/traework2api`：持续维护的Go实现，自述协议来自实测/捕获，包含真实SSE fixture、工具调用修复和模型接口。
- `laojichao/trae-local-api`：`dsh-trae-api`核心代码的直接上游，但工具/XML兼容层和三端点回退缺少充分实测。
- `dsh-trae-api`：只有两个提交，核心协议未迭代，没有成功反馈；不能作为成功基准。
- 本机Trae日志和动态库：独立确认mchost host、Cloud-IDE-JWT、设备身份、SSE reasoning/tool/usage结构。

## 决策

第一可用Provider采用：

```text
DSH PiAiAdapter
  -> 安全loopback shim
  -> Trae SOLO upstream
  -> POST /api/agent/v3/llm_utils_chat
     function=solo_work_lite
```

模型发现采用：

```text
POST /api/ide/v1/get_detail_param
function=solo_work_lite
```

Raw Chat v2代码保留为研究/未来路径，不接入生产调用链。

## 请求格式

OpenAI输入需转换为：

```json
{
  "messages": [
    {
      "role": "user",
      "content": [{ "type": "text", "text": "..." }]
    }
  ],
  "function": "solo_work_lite",
  "stream": true,
  "config_name": "glm-5.2",
  "model": "glm-5.2"
}
```

工具转换：

- OpenAI assistant `tool_calls[].function` -> SOLO `tool_calls[].function_call`
- SOLO output `function_call` -> OpenAI `function`
- `tools[].function.parameters`对象在上行时序列化为JSON字符串
- 不再使用自造`<tool_call>` XML作为首选方案

## SSE

实测事件：

- `metadata`
- `timing_cost`
- `output`：`response`、`reasoning_content`、`tool_calls`
- `extra_info`
- `token_usage`：包含`reasoning_tokens`
- `done`：`finish_reason`
- `error`

## Header

除现有认证、版本、设备Header外，必须补充：

- `X-Ide-Token`
- `User-Agent: Trae/<version>`

## 思考强度

Trae框架支持`minimal/low/medium/high/xhigh`，但必须按模型详情中的`reasoning_effort_options/default_reasoning_effort`动态开放；未声明能力时不发送。SOLO模型接口若未返回这些字段，则继续保持未知，而不是硬编码。

## 否决方案

- 三端点同body自动回退
- 将`/api/ide/v1/chat`作为猜测回退
- 第一阶段复刻完整`create_agent_task`
- 在没有模型声明时为所有模型开放五档思考强度
