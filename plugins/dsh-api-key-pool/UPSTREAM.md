# 上游来源与本地差异

## 固定来源

- 仓库：<https://github.com/xiaozhe7772222/dsh-api-key-pool>
- 固定提交：`ce5fbe824552527b1c6433a350b8272962ae1986`
- 上游版本：`0.3.0`
- 本地版本：`0.3.0-metamath.3`
- 许可证：MIT，许可证文本见 [`LICENSE`](./LICENSE)

## 接入原则

本目录不是把上游应用原样嵌入 DSH，而是保留其“多 Key 调度、并发槽、冷却、熔断和状态统计”领域语义，按 DSH 0.1.1-rc.2 的 Cordis 插件、`PiAiAdapter`、Typert 设置页和 `Remote` 路由契约重写适配层。

| 上游能力 | 本地实现 | 明确不引入 |
| --- | --- | --- |
| 多 Key 调度 | `src/pool.js`、`src/key-state.js` | 示例 Key、环境变量注入 |
| 并发与等待队列 | `src/keyed-slot.js`、`src/pool.js` | 无限重试、无限等待 |
| 冷却/熔断 | `src/failure.js`、`src/key-state.js` | 将调用方取消误判为 Key 故障 |
| 状态接口 | `src/routes.js` | 全量 Key、未脱敏凭据 |
| 配置界面 | `src/settings.js`、`src/client.js` | 独立 `pool-config.json`、直接改写 DSH settings |
| Provider 调用 | `src/adapter.js` | 绕过 DSH 的自建原始 REST 客户端 |

## 本地差异

1. 插件名固定为 `@deepseek-harness/dsh-api-key-pool`；日常在原生 `web` 共存，独立 `web-key-pool` 保留为验收环境。
2. 共存模式只注册 `pool-*` adapter，不观察普通 Provider；独立 Profile 显式启用 fail-closed 守卫。
3. Key 仅存入 DSH Credentials；配置只保存凭据引用，不在源码、日志、接口或页面中回显全量 Key。
4. 每个流式请求通过 `AsyncLocalStorage` 固定一个 Key，直到流结束才释放并发槽。
5. 401/403 禁用 Key，429/速率限制进入冷却，5xx/网络故障累计后熔断；调用方主动取消不惩罚 Key。
6. 仅做有界切换；所有 Key 不可用时返回明确失败，不进行无限重试。
7. Typert 设置卡片的填写方式对齐原生「设置 → 模型」：主字段是单一只写的 API 密钥输入框，端点／协议／模型收在折叠的「自定义设置」，模型目录是原生同款逐行编辑器（模型 ID + 显示名称 + 容量折叠 + 识图（图片输入）+ 删除 + 添加模型，容量沿用 K/M 词表）；识图勾选贯通 Typert、settings、Host 回读与 `PiAiAdapter`，勾选时声明 `input: [text, image]`，未勾选时仍只允许文本。与原生唯一的差别是同一张卡片可以填入多枚 Key。Provider ID 由显示名或端点主机名自动派生，编辑态固定不可改。健康接口仅返回脱敏统计。
8. Profile 依赖使用本地 `file:` 坐标，原生 Profile、原生启动脚本和官方包保持不变。
9. 本地测试额外覆盖 100 个并发流、5 个 Key 的均匀分配与单流 Key 不变性。
10. `apiKeyPool.list` 的池快照额外回读 `api`、`baseURL` 与每个模型的 `contextWindow`/`maxTokens`/可选 `input`（均为 settings 非秘密元数据），使一张卡片能像原生那样改完端点、模型容量和识图能力；递归 secret 扫描与脱敏边界不变。

## 升级方法

1. 在临时目录检出新的上游 tag/commit，先复核许可证、配置格式、调度语义和安全边界。
2. 对照本文件逐项重放必要语义，不覆盖本地 DSH 适配层。
3. 更新 `package.json` 的本地版本后执行 `npm run check` 与 `npm test`。
4. 刷新原生 Profile 的 `file:` 安装产物：`pnpm remove @deepseek-harness/dsh-api-key-pool` 后 `pnpm add file:../../../plugins/dsh-api-key-pool`，再把 `package.json`/`pnpm-lock.yaml` 中被 pnpm 改写成反斜杠的 specifier 还原为 `file:../../../plugins/dsh-api-key-pool`，最后逐文件比对 `node_modules` 与 `lib/` 的 SHA-256。**只递增版本号或 `pnpm install --force` 都刷不动已复制的 `lib/`**（pnpm 复用旧 inode 快照），这是本目录反复出现「代码改了页面没变」的根因；独立 `web-key-pool` Profile 是 Junction，`npm run build` 后即时生效，无需重装。
5. 分别 dump 原生与号池 Profile，确认插件只出现于号池 Profile；再完成 3080/3081 双实例和真实浏览器验收。
6. 更新本文件的固定提交、本地差异及维护记录。

## 回滚方法

日常接入回滚：从 `.dsh/profiles/web/package.json` 移除号池 dependency/bundle 并重新安装。独立验收环境回滚：停止 3081 并移除 `.dsh-key-pool/profiles/web-key-pool` 的接线。两种回滚都保留 Credentials 与运行数据，禁止删除用户凭据。
