# Trae 模型管理与专属能力设计

## 目标

在 DSH 的「设置 → 模型 → Trae → 编辑」中提供符合 DSH 原生体验的模型管理能力：

1. 刷新 Trae 当前可用模型；
2. 从候选模型中选择并保存；
3. 手动增加、编辑和删除模型；
4. 展示模型上下文窗口和最大输出；
5. 逐模型展示可选推理强度；
6. 在取得真实上游数据后展示积分消耗倍率和 1M 上下文能力。

## 插件边界（强约束）

- 本项目只是独立插件，**不得修改 DSH 本体**。
- 不替换、不接管 DSH 全局「模型」设置页或全局模型选择器。
- 不修改其他 provider 的注册、配置或界面体验。
- DSH 自动生成的「模型 → Trae」条目和兜底提示保持原样。
- 所有可编辑的 Trae 专属能力只放在 `dsh-connect-trae` 自己的「插件配置」卡片中。
- 插件只通过公开的 settings、LLM adapter、model discovery 和 provider catalog 接口影响自己的 `trae` provider。

## 设计原则

- 优先复用 DSH 公开的 settings 和 `llm.discoverModels` 能力，不接管或替换任何全局 UI。
- 模型列表属于 Trae provider 配置；保存后同步刷新 provider catalog。
- 思考强度只在 Trae 模型元数据明确公布时开放，不虚构档位。
- 积分倍率与 1M 上下文只展示已验证的上游数据；未取得真实字段时显示“待上游确认”或暂不展示。
- 不把 access token、refresh token、邮箱、手机号或稳定用户 ID 传到浏览器。
- DSH 当前工作目录不作为 Trae 云端可访问路径处理；它由 DSH system prompt/消息上下文告知模型，文件访问仍必须通过 DSH 工具完成。
- 模型调用只允许经过能返回结构化 `tool_calls` 的 `llm_utils_chat` 路径；不得用只提取最终文本的远程会话轮询桥替代。

## 首版效果

```text
Trae
├─ 当前登录账号 / token 过期时间
├─ 模型列表                         [恢复默认] [刷新模型]
│  ├─ DeepSeek-V4-Flash
│  │  └─ ID / 名称 / 168K / 32K / 输入模态
│  ├─ DeepSeek-V4-Pro
│  └─ ...
├─ [+ 手动添加模型]
└─ [取消] [保存]
```

刷新模型时，调用 Trae 模型目录接口，将结果作为候选项交给用户勾选；刷新本身不直接覆盖已保存列表。

## Trae 模型元数据来源

模型刷新以 **Remote 能力目录为骨架**，模型调用仍独立使用能返回结构化 `tool_calls` 的 `llm_utils_chat`：

1. **主源（模型骨架）**：Remote `/models` 目录提供展示 id、展示名、上下文窗口、Max 窗口、积分倍率、推理档位与 multimodal：
   ```text
   GET https://solo.trae.cn/api/remote/v1/models?functions=solo_agent_remote,solo_work_remote
   ```

2. **补充源（wire id 映射）**：`get_detail_param` 只用于解析每个展示名对应的真正 `config_name`（`llm_utils_chat` 接受的 id），不决定模型列表本身：
   ```text
   POST https://trae-api-cn.mchost.guru/api/ide/v1/get_detail_param
   function = solo_work_lite
   ```

两者按**展示名 / config_name** 两级 join：Remote 目录是骨架（`id`/名称/上下文/积分/推理），`get_detail_param` 只附加 `wireConfigName`。join 优先级：

1. `wire.config_name` == remote `id`（多数情况，两者相同，无需 `wireConfigName`）；
2. `wire.display_name` == remote 展示名（历史改名场景，`wireConfigName` 记为 config_name）。

**关键约束（2026-08-30 实测）**：Remote 目录里存在 `get_detail_param` 里**没有对应 `config_name`** 的模型（`Doubao-Seed-Code`、`glm-5.3`），这类模型对 `llm_utils_chat` 必然返回 `4001 "param is invalid"`。因此 join 不到任何 wire 行的 remote 行必须**从目录剔除**，不能对外暴露一个每次调用都失败的模型。

> 为什么需要 `get_detail_param` 补充 wire id：两套接口对同一模型使用不同 id。只有 `get_detail_param` 的 `config_name` 才是 `llm_utils_chat` 真正接受的 id，Remote 目录的 `name` 只是展示名。2026-08-30 实测 `Doubao-Seed-Code`（Remote 展示 id）已经**不是**任何 `config_name`——Seed-Code 已下线/改名（现为 `Doubao-Seed-2.0-Code`、`seed-code-pro-0430`），发 `config_name=Doubao-Seed-Code` 必失败。

已验证字段映射：

| 来源 | Trae 字段 | 用途 |
| --- | --- | --- |
| remote | `name` | DSH 模型 id（展示 id） |
| remote | `display_name` | 模型展示名 |
| remote | `context_window_tokens.dev` | 默认 DSH 上下文预算 |
| remote | `context_window_tokens.max` + `max_mode:true` | 可选的 Max 上下文预算；不生成第二个模型 id |
| remote | `features` 二次 JSON 解析后的 `consumption_rate.data.rate` | 积分消耗倍率 |
| remote | `reasoning_effort_config.options` / `default_level` | 推理强度档位 |
| remote | `multimodal` | 文本/图片输入能力（仅展示，不作为图片授权依据） |
| wire | `config_name` | `wireConfigName`：发往 `llm_utils_chat` 时替换展示 id 的 wire id |
| wire | `display_config.display_name` | join 用的展示名 |
| wire | `model_detail_list[].prompt_max_tokens` | wire 侧上下文窗口（`get_detail_param` **没有** `max_input_tokens` 字段） |
| wire | `model_detail_list[].max_tokens` | wire 侧最大输出（**没有** `max_output_tokens` 字段） |
| wire | `model_detail_list[].model_name` | 底层 checkpoint 名（带 `__dev`/`__max` 后缀），**不是** `llm_utils_chat` 接受的 `config_name`，不可用于请求 |

Remote 目录客户端不提供聊天方法；`TraeSoloRemoteBridge` 和 Remote 会话创建/轮询逻辑已删除，避免再次混用两个不兼容的协议族。

PiAiAdapter 的内部档位映射仅用于适配层，发往 Trae 时还原其原始值：

```text
Trae light      <-> PiAi low
Trae high       <-> PiAi high
Trae extra_high <-> PiAi xhigh
```

UI 直接显示 DSH 档位标识 `low / high / xhigh`，与同系列 WorkBuddy 卡片一致。未返回 `reasoning_effort_config` 的模型只记录“支持推理”，不虚构档位。

## 后续模型详情

```text
Qwen3.8-Max
├─ 积分消耗速度：1.50 倍（只读）
├─ 支持的思考强度：low / high / xhigh
├─ 默认思考强度：high
└─ DSH 上下文预算：200K / 1M
   └─ 一个模型 id，按预算调整 DSH 的有效上下文，不生成 @1m 变体
```

## 实施阶段

### 阶段 1：原生模型管理

- Trae 设置 Schema 暴露 `models` 数组；
- 注册 `llm` 模型发现回调；
- 使用当前登录 Trae 账号读取模型候选；
- 保存配置后更新运行时 catalog；
- 保留保守的内置模型作为默认列表。

### 阶段 2：能力元数据

- 从 Trae 模型详情恢复：`reasoning_effort_options`、`default_reasoning_effort`；
- 映射为 DSH 原生 reasoning metadata；
- 在 DSH 模型选择器中自动显示推理强度。

### 阶段 3：Trae 专属能力

- 恢复并验证积分消耗倍率字段；
- 恢复并验证 Max 上下文支持字段；
- 仅对支持的模型展示默认 / Max 上下文预算单选；
- 一个上游模型只注册一个 DSH 模型 id，不生成 `@1m` 变体；
- 验证推理强度和上下文预算真实进入 DSH 模型元数据。

## 验收标准

- Trae 的模型编辑卡片可刷新、增加、编辑、删除并保存模型；
- 刷新失败不破坏现有模型列表；
- 模型列表变化后 DSH provider catalog 同步更新；
- 不影响其他 provider 的模型设置体验；
- 未验证的倍率、推理强度和 Max 上下文能力不得伪造；模型目录中不得出现 `@1m` 变体。
