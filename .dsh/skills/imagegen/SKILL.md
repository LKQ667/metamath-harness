---
name: imagegen
description: DeepSeek Harness 专用的手动图像生成 Skill。用于文生图、参考图引导生成、论文概念图和普通插画；直接调用已配置的原生 image_generate 工具，将结果保存到工作区并在会话前端显示。
user-invocable: true
disable-model-invocation: true
---

# ImageGen

## 用途

这个 Skill 负责“真正生成图片”。它不替代只做配图规划的 `/ai-draw-skills`，也不把普通聊天模型、PIL、SVG 或占位框当作生图结果。

## DeepSeek Harness 入口契约

仅由用户手动调用。若输入包含 `dsh.mathmodel.request/v1`，其 `skill` 必须为 `imagegen`；直接消费卡片锁定的 `prompt`、`connection_id`、`aspect_ratio`、`size`、`count`、`reference_images`、`output_dir` 和 `confirm_paid_call`，不得重复询问。

- `connection_id` 留空时省略 `connectionId`，使用设置页已选定的当前生图连接；填写时只传该 `connectionId`。不得按供应商顺序或失败自动换用其他连接。
- `size` 为“模型默认”时省略工具参数；其他值原样传入。
- `reference_images` 按换行或逗号拆成工作区相对路径数组，最多 4 张；不得读取工作区外图片。
- `output_dir` 默认 `.`（当前选择的工作区文件夹），可自定义工作区内的相对目录，但不得越出工作区。
- `count` 必须为 1–4。

## 固定工作流

1. 确认本轮用户明确要求生成图片，并且 `confirm_paid_call` 为 `true`；两者缺一时，在调用前停止并说明需要本次授权。
2. 直接原生调用一次 `image_generate`，传入 Prompt、可选 connectionId、参考图、比例、尺寸、数量、输出目录与 `authorizePaid: true`。
3. 不使用 `run_code`、PowerShell 或后台任务包裹该调用，确保图片展示元数据进入当前会话。
4. 成功后简短报告连接、模型、数量和工作区相对路径；图片由工具结果直接显示，无需再嵌入 base64 或文件 URL。
5. 失败时原样概括脱敏后的供应商错误；不得用本地绘图补一张假结果。只有工具明确返回 `fallback` 时，才可将提示词交给 `/ai-draw-skills`，并标明“未生成图片”。

## 编辑与参考图

当前工具支持以 1–4 张工作区本地图片作为视觉参考，但不提供蒙版局部编辑。用户要求精确局部修改而供应商不支持时，应说明限制并生成“参考图引导的新版本”，不得声称完成了像素级编辑。

## 安全边界

- Key、Base URL 和模型只从“设置 > 模型 > 生图模型”读取，绝不写入 Prompt、文件或日志。
- 卡片勾选只授权当前一次调用，不得复用于下一轮。
- 生图连接独立于对话模式；任意模式只要已加载本插件都可调用原生 `image_generate`。若工具未加载，只提示重启 Harness 或检查插件，不要求切换模式、搜索环境变量或重复粘贴 Key。
- 不承诺供应商一定成功，不伪造检测结果、费用、模型名称或图片路径。
