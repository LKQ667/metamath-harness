---
name: claude-vision-skill
description: 为不具备原生识图能力的 DeepSeek Harness 模型提供手动触发的视觉配置与识图流程。仅当用户明确点名 `claude-vision-skill` 时使用 DSH 原生 `vision_analyze` 工具；不读取 Skill `.env`，不直接运行旧 `vision.js`。
user-invocable: true
disable-model-invocation: true
---

# 识图能力（vision）

你的底层模型可能不具备原生识图能力。在 DeepSeek Harness 中只调用原生 `vision_analyze` 工具，不使用 Read 读取图片内容，也不直接运行本目录的旧 `vision.js`。

```text
vision_analyze({ image: "<当前工作区内的相对图片路径或 HTTPS URL>", prompt: "用中文描述这张图片" })
```

## 手动触发方式

- 用户必须明确点名本技能，例如：`$claude-vision-skill 分析这张图片`。
- 即使用户分享图片路径或要求分析图片，也不要自动触发本技能；用户可直接使用已配置的原生视觉工具，或明确点名本 Skill。

## mathmodel 卡片契约

若调用文本包含 `dsh.mathmodel.request/v1`，其 `skill` 必须为 `claude-vision-skill`。直接消费锁定的 `dashscope_key_status`、`primary_model`、`fallback_model`、`test_image`、`run_connectivity_test`、`beginner_guide` 和 `userNotes`，不得重复询问，也不得把凭据状态字段当作 Key 正文。

主模型固定为 `qwen3.7-plus`，失败后由 Host 自动回退到 `qwen3.7-flash-2026-07-15`。模型顺序属于工具契约，Skill 不通过 Prompt、环境变量或文件覆盖。

## 用法

本地图片必须位于当前工作区，传相对路径：

```text
vision_analyze({ image: "figures/example.png", prompt: "用中文详细描述这张图片" })
```

网络图片：

```text
vision_analyze({ image: "https://example.com/image.jpg", prompt: "用中文详细描述这张图片" })
```

远程图片只允许 HTTPS。多张图片逐张调用并保留图片与描述的对应关系；任何失败都报告真实错误，不假装已经识图。

## 配置

1. 在卡片的“百炼 Key 状态”字段点击安全保存；Key 由 DSH 凭据服务保存为 `DASHSCOPE_API_KEY`，不会进入 Prompt、普通设置或错误报告。不要要求用户把 Key 粘贴到对话文本。
2. 保存后回到原卡片查看“已配置”状态，其他已填字段保持不变。
3. 若 `run_connectivity_test=true` 且 `test_image` 有值，用该工作区图片调用一次 `vision_analyze`。没有测试图片时只说明尚未测试，不编造连通成功。
4. `beginner_guide=true` 时用通俗中文显示以上步骤、百炼控制台用途、按量计费提示和常见错误（Key 未配置、图片越界、网络失败、主备模型均失败）。不得展示 Key 正文。

## 旧配置迁移边界

本目录可能存在旧 `.env`，DSH 与本 Skill 均不得读取、复制、移动、改写或删除它，也不得把其中内容迁移到对话。先通过卡片安全配置新凭据并完成真实连通性验证；之后只提示用户如有需要可自行清理旧文件。旧 `vision.js` 仅供非 DSH 独立环境兼容，且只读取显式进程环境变量。

## 注意

- 多张图片时逐张调用 `vision_analyze`，拿到全部文字描述后再回复用户。
- 识图调用在百炼平台按量计费，正常单张图片成本极低。
