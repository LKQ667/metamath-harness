# 上游来源与本地适配

- 上游仓库：<https://github.com/NinjaSln-labs/dsh-plugins/tree/main/dsh-knowledge-sqlite>
- 固定提交：`ac638c38b8eda56947ce2d997ffc4f50d432763d`
- 上游版本：`0.1.6`
- 本地版本：`0.1.6-metamath.1`
- 许可证：上游 `package.json` 声明 `MIT`；固定提交未附独立 LICENSE 正文，发布或再分发前必须复核上游许可证文件。

## 本地差异

1. `gating: ask` 同时覆盖 `knowledge_write`、`knowledge_update` 和 `knowledge_delete`，避免更新绕过用户确认。
2. 新增 `registerProbeTool` 配置；正式 Profile 设为 `false`，不向模型暴露实验语料探针。
3. 正式 Profile 关闭查询扩展，检索不产生隐式模型调用；global 写入名单保持为空。
4. 数据库固定到 `$DSH_HOME/data/knowledge.sqlite`，不进入源码归档。
5. 使用 `node:path.isAbsolute()` 识别语料路径，修复 Windows 盘符绝对路径被错误拼到工作区路径后的问题；冒烟脚本动态导入也统一转换为 `file://` URL。

## 构建与验证

```powershell
npm install
npm run build
npm run typecheck
npm test
```

升级上游时以本固定提交为旧上游、新版本为新上游、本目录为本地改造做三方比较。先重放上述四项差异，再验证工具名、`ctx.knowledge` 服务、ask 门控和 SQLite 运行时。

## 回滚

从 Web Profile 的依赖和 bundles 中移除 `dsh-knowledge-sqlite`，重新运行 `pnpm install` 并重启。默认保留 `.dsh/data/knowledge.sqlite`；未经明确授权不得删除。
