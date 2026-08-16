# DeepSeek Harness Skill Installer

这是 DeepSeek Harness（DSH）专用的 GitHub Skill 安装工具，目标目录固定遵循官方 `$DSH_HOME/skills` 结构。

## 本机位置

```text
DSH_HOME = <便携根目录>\data\dsh-home
Skill 根目录 = <DSH_HOME>\skills
本工具 = <DSH_HOME>\skills\skill-installer
```

DSH 直接扫描 Skill 根目录的下一层：

```text
$DSH_HOME\skills\
├── skill-installer\
│   └── SKILL.md
└── another-skill\
    └── SKILL.md
```

不要把 Skill 放成 `$DSH_HOME\skills\某个集合\skill-name\SKILL.md`，额外嵌套会导致 DSH 无法识别。

## 文件说明

| 路径 | 用途 |
|---|---|
| `SKILL.md` | DSH 读取的触发描述、安装流程和行为约束 |
| `scripts/list-skills.py` | 从 GitHub 目录列出 Skill，并标记本机已安装项 |
| `scripts/install-skill-from-github.py` | 下载并安装包含 `SKILL.md` 的 GitHub 目录 |
| `scripts/github_utils.py` | GitHub API 请求及可选令牌处理 |
| `agents/openai.yaml` | 上游兼容的显示元数据；DSH 核心识别不依赖此文件 |
| `assets/` | Skill 图标资源 |

## 常用命令

在本目录执行：

```powershell
python scripts/list-skills.py
python scripts/list-skills.py --format json
python scripts/install-skill-from-github.py --repo owner/repo --path path/to/skill
python scripts/install-skill-from-github.py --url https://github.com/owner/repo/tree/main/path/to/skill
```

默认安装到：

```text
$DSH_HOME\skills\<skill-name>
```

如未设置 `DSH_HOME`，脚本回退到 `~\.dsh\skills`。

## 更新管理

这个目录源自通用 Skill Installer，但已做 DSH 专用适配。以后同步上游版本时，不要直接整目录覆盖，应按以下顺序更新：

1. 备份或提交当前版本。
2. 比较上游 `SKILL.md` 和 `scripts/` 的变化。
3. 只合并通用的 GitHub 下载、校验和安全修复。
4. 保留以下 DSH 专用差异：
   - 使用 `DSH_HOME`，不使用 `CODEX_HOME`。
   - 默认目录为 `~/.dsh/skills`。
   - GitHub User-Agent 使用 `deepseek-harness-*`。
   - 临时目录使用 `deepseek-harness`。
   - Skill 名称限制为小写字母、数字和连字符。
   - 安装完成后提示重载 DSH Skills 或开始新对话。
5. 运行下方验证命令。
6. 在 DSH 中发起“列出可安装技能”的新对话，做一次实际触发测试。

## 验证清单

```powershell
python -m py_compile scripts/github_utils.py scripts/list-skills.py scripts/install-skill-from-github.py
python scripts/list-skills.py --format json
python scripts/install-skill-from-github.py --help
```

同时确认：

- `SKILL.md` 的 `name` 为 `skill-installer`。
- `SKILL.md` 位于本目录顶层。
- 脚本中不存在 `CODEX_HOME` 或 `~/.codex`。
- 未设置 `--dest` 时，安装路径落在当前 `DSH_HOME\skills`。
- 已存在的目标目录不会被覆盖。

## 凭据与安全

- 公共仓库不需要令牌。
- 私有仓库可使用现有 Git 凭据，或环境变量 `GITHUB_TOKEN` / `GH_TOKEN`。
- 不要把令牌写进 Skill 文件、命令示例、日志或版本库。
- 安装前确认来源可信；Skill 的 `SKILL.md` 和脚本都可能包含可执行指令。
