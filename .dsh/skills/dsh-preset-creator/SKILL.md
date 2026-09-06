---

name: dsh-preset-creator
description: 在 DeepSeek Harness (DSH) 下创作新 Agent preset（元模式）：产出 preset.yml + agent.cordis.yml 并验证组装。对任何 agent（Codex/Claude/TRAE/DSH）通用，只需文件读写与命令执行能力。Use when the user asks to create/新建 a DSH 模式、preset、元模式 or "用创造模式做一个模式".
---

# DSH Agent Preset 创作（元模式）

为 DeepSeek Harness 创作一个新的 Agent preset。执行本技能的 agent 只需：读文件、写文件、跑命令。

## 0. 定位 DSH\_HOME

preset 一律写入用户区：`<DSH_HOME>/.agent-presets/<新模式id>/`

- 默认 `~/.dsh`；探测方法：找同时含 `.agent-presets/` 与 `settings.yaml` 的目录

- 本机为 `F:\DeepSeekHarness\.dsh`

## 1. 动手前必读（全部读完再写）

| 参考                       | 位置                                                                                   | 用途              |
| ------------------------ | ------------------------------------------------------------------------------------ | --------------- |
| 官方 cordis preset（"创造模式"） | 官方仓库 `packages/preset/agent-presets/presets/cordis/agent.cordis.yml`                 | 行结构范本（只参考，绝不修改） |
| 官方创作契约技能                 | 同上 `cordis/skills/editing-cordis-compositions` 与 `cordis-plugin-development`         | 写组合前必须遵循        |
| 本机既有 preset              | `<DSH_HOME>/.agent-presets/` 下各目录（极简参照无 agent.cordis.yml 的，完整参照含 agent.cordis.yml 的） | 结构范例            |
| 用户配置                     | `<DSH_HOME>/settings.yaml` 的 `agent-presets` 节                                       | 默认 preset       |

官方仓库：<https://github.com/deepseek-ai/deepseek-harness>

## 2. 产出物

在 `<DSH_HOME>/.agent-presets/<新模式id>/` 下产出两个文件：

**preset.yml**（3 字段）：

```yaml
name: <中文展示名>
description: <一句话：该模式的范式与能力>
order: <排序整数>
```

**agent.cordis.yml**（按 cordis preset 的行结构组装插件行）：

- 仅当需要运行时自扩展（元模式）时，显式加入两行：
  `- name: '@deepseek-ai/dsh-cordis-host-runner'` 与 `- name: '@deepseek-ai/dsh-tool-cordis'`

- 否则只组装该模式实际需要的工具/persona/prompt 行

## 3. 硬性规则

1. **双平面原则**：跨会话共享的服务/注册表 → HOST 组合；单会话贡献的工具、persona、prompt sections → AGENT PRESET
2. **禁止编辑/删除出厂 preset**；要改内置行为，只能复制组合到新目录改副本
3. **信任边界**：preset 权限 = 所引用插件的权限 ≈ shell 访问。官方 `@deepseek-ai/*` 行可信；第三方插件行必须核查来源后才可引用
4. **Windows 平台**：工具行用 `@deepseek-ai/dsh-tool-pwsh`，不用 bash

## 4. 验收与启动

```powershell
dsh --dump-config   # 新 preset 应出现在名单且无组装错误
```

启动方式（二选一，写入交付汇报）：

- 新建会话时选择该 preset；已有会话在未产出任何内容前可切换

- 或把 `settings.yaml` 的 `agent-presets.default` 改为新模式 id（需用户确认）
