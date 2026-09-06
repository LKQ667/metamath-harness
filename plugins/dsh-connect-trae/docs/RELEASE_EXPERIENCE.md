# DSH 插件发布经验备忘（复用自 dsh-subagent-default-model）

> 本文档把团队已验证项目 `dsh-subagent-default-model` 的发布与插件工程经验浓缩成可复用备忘，
> 供 `dsh-connect-trae` 及后续 DSH 插件项目同步。
> 权威发布流程仍以本仓库根目录 [`RELEASING.md`](../RELEASING.md) 为准；本文档是「为什么这么做 + 别踩的坑 + 环境配置」。

## 1. 本机 git / npm 环境配置（一次性，首次发布前确认）

> ⚠️ 这些是发布提交/打 tag 时依赖的环境配置，属于「手动填写一次」的项。换新机器或新项目时先核对。

### 1.1 git 提交署名（user.name / user.email）

发布流程里的 `git commit` / `git tag` 会带上提交作者，GitHub 上显示的名称和邮箱来自这里。

```bash
git config --global user.name  "LaoDing"
git config --global user.email "shangxinyu2002@gmail.com"
```

- **必须与 LICENSE 版权归属一致**：本项目 LICENSE 版权为 `Copyright (c) 2026 LaoDing`，提交署名 `LaoDing` 与之一致，不要改成 npm 账号或其它名称。
- 若某仓库想用不同署名，可在该仓库内 `git config user.name/email` 设置 local 级；否则默认继承全局。

### 1.2 git 代理（访问 GitHub 用）

本机访问 GitHub 走本地代理 `127.0.0.1:7897`：

```bash
git config --global http.https://github.com.proxy http://127.0.0.1:7897
```

- npm 侧同理（`~/.npmrc` 配置了代理），`npm publish` / `npm install` 才能访问 npm registry。
- 在其它机器发布且能直连时，无需代理配置。

### 1.3 npm 登录

```bash
npm whoami   # 应显示 dmh2002；若报 need auth，先 npm login
```

### 1.4 一键核对清单

```bash
git config --global user.name
git config --global user.email
git config --global --get http.https://github.com.proxy
npm whoami
```

四项输出应分别为：`LaoDing`、`shangxinyu2002@gmail.com`、`http://127.0.0.1:7897`、`dmh2002`。

## 2. 发布流程要点（速查）

完整步骤见根目录 `RELEASING.md`，此处只列关键纪律：

1. **发布前**：跑完整检查（本项目 `pnpm run check`：typecheck + test + build）；核对 LICENSE 版权仍是 `Copyright (c) 2026 LaoDing`。
2. **版本号**：只改 `package.json` 的 `version`；CHANGELOG 顶部新增 `## X.Y.Z (YYYY-MM-DD)`，按 Features / Fixes / Docs 分组。
3. **tag 纪律**：`git tag -a vX.Y.Z -m "..."` 必须是 **annotated tag**；tag 必须指向包含本次代码的提交。
   - 若误打 tag 指向旧提交：`git tag -d vX.Y.Z` → 重打 → `git push -f origin vX.Y.Z`，再用 `git rev-list -n1 vX.Y.Z` 确认指向 HEAD。
4. **打包白名单**：`package.json` 的 `files` 字段已限定发布内容（`lib/`、`cordis.patch.yml`、README 双语、CHANGELOG、THIRD_PARTY_NOTICES、LICENSE、截图等）；`npm pack --dry-run` 核对无秘密、无测试垃圾、无本地路径。
5. **npm publish 与 2FA**：账号开 2FA 时 `npm publish` 会报 `EOTP` 并给出浏览器 URL，打开确认即可；不要绕过 2FA。
6. **发布后验证**：`npm view dsh-connect-trae version` 与 `dist-tags.latest`；刚发布后 registry 读缓存有短暂延迟，稍等重查。
7. **权限边界**：commit / tag / push / npm publish / 市场提交，都必须在用户明确确认后执行。

## 3. DSH 插件工程红线（来自 dsh-subagent-default-model 踩坑总结）

这些红线是 DSH 插件能否被正确识别、设置行能否出现、更新能否生效的关键：

1. **`package.json` 必须暴露 `./package.json`**（exports 里要有 `"./package.json": "./package.json"`）→ 否则 dsh-client-modules 扫描会跳过该插件，设置行不出现。
2. **客户端 `inject` 必须包含所需服务**（settings 行激活必需 `connection`、`slots`；本项目还注入 `locale`、`settingsScope`、`remote` 等）→ 少了则设置卡片不渲染。
3. **设置 namespace 无需白名单**：DSH 0.1.1-rc.2 起 `dsh-host-apiproxy` 已移除 `WEB_SETTINGS_NAMESPACES` 白名单，`settings.describe` 直接返回全部已注册 namespace → 无需任何 patch。
4. **首次注册只做一次**：`dsh plugin --profile desktop add /路径` 以 `link:` 安装，重复注册会重装依赖树 → 不要重复执行。
5. **更新后必须重启 DSH 进程**：bundle patch 与 host/client 半边在启动时加载 → 改代码 / 装新版本后重启 DSH Desktop（⌘Q → 重开）才生效；仅改 settings.yaml 是热加载，无需重启。
6. **本地开发用 `link:`，不重装依赖树**：`dsh plugin --profile desktop add ~/DshProject/dsh-connect-trae`，node_modules 里是源码软链，改码后重启生效；不要在 desktop profile 里手动跑 `pnpm install` 重装整树。
7. **cordis.patch.yml 只做最小插入**：注册插件 id 即可，如本项目 `- insert: - id: dsh-connect-trae / name: dsh-connect-trae`，不改 profile 默认模型。
8. **license / copyright 字段**：`package.json` 的 `license: "MIT"`、`copyright: "Copyright (c) 2026 LaoDing"` 与根 LICENSE 三者保持一致；README「许可证」章节应写全（协议 + 版权归属 + 概要 + 指向 LICENSE），不要只留一行 `[MIT](LICENSE)`。

## 4. 发布后验证（DSH 侧）

- 在干净 profile 从 npm 安装：`dsh plugin --profile desktop add dsh-connect-trae`（或 `cd ~/.dsh/profiles/desktop && npm install dsh-connect-trae`），重启 DSH Desktop。
- 确认：设置 → 插件配置 → DSH Connect Trae 卡片出现、provider 注册（模型选择器出现 Trae 模型）、短流式对话可用、用量概览只读可读。

## 5. 常见问题

| 问题 | 原因 | 解决 |
| --- | --- | --- |
| 设置卡片不出现 | 插件未装入 profile / 未重启 / exports 缺 `./package.json` | `dsh plugin --profile desktop add` 后重启 DSH Desktop；核对 exports |
| 保存按钮灰色 | 必填字段未填全 | 填满所有必填路由字段 |
| `npm publish` 报 EOTP | 账号开启 2FA | 按 npm CLI 给的 URL 在浏览器确认 |
| 发布后 `npm view` 还是旧版本 | registry 读缓存延迟 | 稍等重查 `npm view ... versions` |
| 子代理 / provider 用父模型 | provider 或 model 缺失 | 确保 provider 和 model 都填写 |

---

*本文档为经验备忘，来源：`dsh-subagent-default-model`（本机 `../dsh-subagent-default-model`，GitHub `dingminhua/dsh-subagent-default-model`）。新增经验请继续追加，保持与根目录 `RELEASING.md` 的权威流程一致。*
