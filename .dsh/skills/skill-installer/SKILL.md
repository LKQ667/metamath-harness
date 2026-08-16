---
name: skill-installer
description: 为 DeepSeek Harness（DSH）列出和安装 Agent Skills。用户要求查看可安装 Skill、从 openai/skills 精选目录安装 Skill，或从任意 GitHub 仓库路径安装 Skill（含私有仓库）时使用。默认安装到 $DSH_HOME/skills；未设置 DSH_HOME 时使用 ~/.dsh/skills。
---

# DeepSeek Harness Skill Installer

为 DeepSeek Harness 安装符合 `SKILL.md` 目录规范的 Skill。默认来源为 `openai/skills` 的 `skills/.curated`；用户也可以指定其他 GitHub 仓库和目录。

## 工作流程

1. 用户询问可用 Skill 或未指定具体操作时，运行列表脚本。
2. 用户提供精选 Skill 名称时，从 `openai/skills` 对应目录安装。
3. 用户提供 GitHub 仓库或目录链接时，从指定来源安装。
4. 安装后报告实际目标路径，并提醒重新开始一个 DSH 对话或重载 Skills 后使用。

## 脚本

- 列出精选 Skill：`python scripts/list-skills.py`
- 输出 JSON：`python scripts/list-skills.py --format json`
- 列出其他目录：`python scripts/list-skills.py --repo <owner/repo> --path <repo/path>`
- 按仓库目录安装：`python scripts/install-skill-from-github.py --repo <owner/repo> --path <path/to/skill> [<path/to/skill> ...]`
- 按 GitHub URL 安装：`python scripts/install-skill-from-github.py --url https://github.com/<owner>/<repo>/tree/<ref>/<path>`

这些脚本会访问网络。遇到访问限制时，说明原因并停止；不得输出令牌或凭据。

## 安装规则

- 默认目标为 `$DSH_HOME/skills/<skill-name>`。
- 未设置 `DSH_HOME` 时，使用 `~/.dsh/skills/<skill-name>`。
- DeepSeek Harness 只从 Skills 根目录直接识别 Skill，不要额外嵌套一层目录。
- 待安装目录必须包含顶层 `SKILL.md`。
- Skill 名称必须使用小写字母、数字和连字符，并与目标目录名一致。
- 目标目录已存在时中止，不覆盖用户现有 Skill；更新操作应先比较差异，再由用户明确要求处理。
- 公共仓库默认直接下载；遇到鉴权或权限错误时回退到 Git sparse checkout。
- 私有仓库仅使用用户已有 Git 凭据或 `GITHUB_TOKEN` / `GH_TOKEN`，不得回显凭据。
- 支持 `--ref <ref>`、`--dest <path>`、`--method auto|download|git`；单个 Skill 可用 `--name` 指定目标名称。

## 输出格式

列出 Skill 时说明来源，并标注已安装项。例如：

```text
来自 owner/repo/path 的 Skills：
1. skill-one
2. skill-two（已安装）
```

安装完成后说明 Skill 名称、实际路径和是否需要重载。发生错误时保留原目录，给出可操作的错误原因。

