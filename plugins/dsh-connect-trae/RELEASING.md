# 发布流程（Release Flow）

> 本文档是 `dsh-connect-trae` 的**唯一权威发布流程**。发布前请通读一遍。

## 前置条件

- npm 已登录：`npm whoami` 应显示 `dmh2002`（若报 `need auth`，先 `npm login`）。
- 账号若开启 2FA（两步验证）：`npm publish` 时需**在浏览器确认一步**。
- GitHub 仓库：`https://github.com/dingminhua/dsh-connect-trae`（默认分支 `main`）。
- 网络：本机已配置代理 `127.0.0.1:7897`（git 与 npm 均已配置；若在其他机器发布，直连即可）。

## 每次发布的完整步骤

### 1. 确认代码、测试与版权

```bash
cd ~/DshProject/dsh-connect-trae
pnpm run check        # typecheck + test + build，应全部通过
grep -F "Copyright (c) 2026 LaoDing" LICENSE
```

> 本项目以 MIT 许可证发布，版权归属必须保持为 **LaoDing**；发布前不得把 LICENSE 中的版权主体改成 npm 账号、GitHub 账号或其他名称。

### 2. 更新版本号

手动改 `package.json` 的 `version` 字段。

> 后续步骤以目标版本号 `X.Y.Z` 指代。

### 3. 更新 CHANGELOG.md

在 `CHANGELOG.md` 顶部新增一节 `## X.Y.Z (YYYY-MM-DD)`，按 `Features` / `Fixes` / `Docs` 分组记录本次变更。

### 4. 提交并打 git tag

```bash
git add package.json CHANGELOG.md README.md README.en.md
git commit -m "chore: 版本升级至 X.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z: <一句话说明>"
git push origin main
git push origin vX.Y.Z
```

> ⚠️ **tag 必须指向包含本次代码的提交**。若目标 tag 已存在且指向旧提交，需先删除并强制移动，修正后用 `git rev-list -n1 vX.Y.Z` 确认指向当前 HEAD。

### 5. 发布到 npm

```bash
npm publish
```

**打包内容**：`package.json` 的 `files` 字段已限定只发布 `lib/`、`docs/assets/dsh-connect-trae-usage-card.png`、`screenshots.json`、`cordis.patch.yml`、`README.md`、`README.en.md`、`CHANGELOG.md`、`THIRD_PARTY_NOTICES.md`、`LICENSE`，`tests/` 和 `node_modules/` 不会进入发布包。

**发布前检查**（可选但推荐）：

```bash
npm pack --dry-run
```

### 6. 2FA 确认（若账号开启两步验证）

`npm publish` 若提示 EOTP，按 npm CLI 给出的 URL 在浏览器登录确认即可，终端内的 `npm publish` 会自动继续。

### 7. 验证发布成功

```bash
npm view dsh-connect-trae version            # 应显示 X.Y.Z
npm view dsh-connect-trae dist-tags.latest   # 应为 X.Y.Z
```

> 刚发布后 registry 读缓存可能有短暂延迟，稍等重查即可。

## 常见问题

- **`npm publish` 报 EOTP**：账号开启了 2FA，按第 6 步在浏览器确认，不要绕过。
- **发布后 `npm view ... version` 还是旧版本**：registry 缓存延迟，稍等重查 `npm view ... versions`。
- **本地开发与发布的关系**：本地开发用 `link:` 安装，与 npm 发布互不影响；npm 发布的包是 `lib/`、README 等静态文件，同一份源码。
