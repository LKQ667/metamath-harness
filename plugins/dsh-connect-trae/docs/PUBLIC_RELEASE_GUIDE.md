# 对外 README 与发布基准

## 基准项目

`dsh-connect-trae` 的对外展示和发布流程参考团队项目：

- 仓库：<https://github.com/dingminhua/dsh-subagent-default-model>
- 本机目录：`../dsh-subagent-default-model`

这里只复用其成熟的发布工程思路，不复制其内部程序结构。

## README 结构

正式对外 README 应按以下顺序组织：

1. 居中项目截图或品牌图。
2. 居中项目名和一句话价值主张。
3. 中文/英文、安装、配置、更新日志、问题反馈导航。
4. npm version、downloads、CI、license、stars、DSH 市场等徽章。
5. 项目定位和适用范围。
6. 功能亮点。
7. 工作原理和最小调用链图。
8. 效果预览和真实截图。
9. 安装命令，至少覆盖 Desktop，并说明其他 profile 的替换方式。
10. 前置条件：Trae 安装版本、登录状态、支持平台和 DSH 版本。
11. 配置、诊断命令及常见错误。
12. 安全说明：凭据只读、不会打印或提交 token、本地 shim 的边界。
13. 已知限制：私有上游协议可能变化、首阶段支持范围、工具调用状态。
14. 开发和验证命令。
15. 卸载方法。
16. 免责声明和许可证。

根 README 用于 GitHub；npm 包中同步提供中文 `README.md` 和英文 `README.en.md`。不得在功能尚未通过自动化测试和 live E2E 时宣传“完整支持”。

## npm 包要求

`package.json` 至少包含：

- `name`、`displayName`、`version`、`description`
- `keywords`、`author`、`license`
- `repository`、`homepage`、`bugs`
- `engines`、`type`、`main`、`types`、`exports`
- `dsh.bundle` 与需要时的 `dsh.client`
- 准确的 peer/dev dependencies
- `files` 发布白名单
- `test`、`typecheck`、`build`、`check`、`prepack` 脚本

发布白名单原则上只包含：

```text
lib/
icons/                 # 如果有 UI 图标
cordis.patch.yml
README.md
README.en.md
CHANGELOG.md
LICENSE
package.json           # npm 自动包含
```

源码是否进入 npm 包由实际调试需求决定；默认不发布测试、研究文档、真实 fixture、`node_modules`、`.env` 或凭据相关文件。

## CHANGELOG

包内维护 `CHANGELOG.md`：

```markdown
## X.Y.Z (YYYY-MM-DD)

### Features
- ...

### Fixes
- ...

### Docs
- ...
```

只记录对使用者有意义的变化。协议、安全或认证路径的变化必须明确标注。

## 权威发布文档

项目根目录在进入发布准备阶段时创建 `RELEASING.md`，作为唯一权威发布流程。内容应基于 `dsh-subagent-default-model/RELEASING.md`，但使用本项目的真实路径、包名、测试命令和账号要求，不能机械复制过时信息。

建议步骤：

1. 确认工作树、分支和远程仓库。
2. 执行完整 `check` 和受控 live E2E。
3. 更新版本号。
4. 更新中英文 README 和 CHANGELOG。
5. 执行 `npm pack --dry-run`，核对 tarball 无秘密、无测试垃圾、无本地路径。
6. 提交版本变更。
7. 创建 annotated tag，确认 tag 指向包含对应版本的提交。
8. 经用户明确确认后 push 分支和 tag。
9. 经用户明确确认并处理 npm 2FA 后执行 `npm publish`。
10. 验证 npm `version`、`dist-tags.latest`、tarball 内容。
11. 从 npm 在干净 profile 安装，验证 provider 注册、模型目录和短流式对话。
12. 必要时创建 GitHub Release 和市场提交。

## 市场提交（Awesome DSH Plugin）

提交给 [Awesome DSH Plugin](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin) 市场（`contributing.md` 为唯一权威流程，以下为要点）：

- **提交位置**：PR 需要在市场仓库的 **`data/plugins/<owner>__<repo>.yml`** 放下一个 yml（不是本项目 `awesome-dsh-plugin-submission/` 目录——那只是本地草稿，提交时以市场仓库 `data/plugins/` 为准）。yml 只含 `url` / `name` / `category` / `description`（见现有草稿 `awesome-dsh-plugin-submission/dingminhua__dsh-connect-trae.yml`）。
- **README 必须生成、禁止手编**：市场仓库两个 README 由脚本生成，提交 yml 后需在其仓库执行 `npm ci` + `node scripts/generate-readme.mjs`，把生成的 README 与 yml 一起提交。手工编辑 README 是常见打回原因。
- **硬性要求自检**：`package.json` 声明 `dsh.bundle`（仅 `dsh.client` 会被拒）；仓库满 1 天且提交数 ≥ 10；仓库带 `dsh-plugin` topic；`description.en` 必填、描述属实、不带营销词；`category` 从指南给定的取值里选最贴切的。
- **截图声明位置**：市场截图在**自己仓库**根目录的 `screenshots.json` 声明（相对路径，1-8 张，见仓库根 `screenshots.json`）；绝对 URL 只接受 GitHub 托管。市场仓库的 `data/screenshots.json` 是旧条目回退文件，**禁止新增键**，也不要在本地造 `screenshots-entry.json` 之类的映射文件。
- **依赖与去重**：依赖须指向原作者仓库或其 npm 包；聚合包只收其中的单个插件，不单独收录；一个 PR 最多 3 个条目。

## 发布门槛

以下条件未全部满足不得发布稳定版本：

- DSH provider 注册集成测试通过。
- auth/decrypt/path 单元测试通过。
- shim 安全加固测试通过。
- SSE fixture 回放测试通过。
- typecheck、build、test 全部通过。
- live E2E 经用户知情后通过。
- 不存在 token、refresh token、用户 ID、账号数据或本机绝对路径泄漏。
- README 的支持范围与实际测试证据一致。
- `npm pack --dry-run` 内容经过人工核对。

## 权限边界

编写 README、CHANGELOG、RELEASING 和生成发布候选包属于开发工作；以下动作必须等待用户明确确认：

- Git commit（若当时治理或用户要求另有门禁，也必须遵守）
- Git tag
- Git push
- GitHub Release
- npm publish
- 市场提交
