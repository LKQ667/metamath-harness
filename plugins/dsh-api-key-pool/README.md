# DSH API Key Pool

基于 [xiaozhe7772222/dsh-api-key-pool](https://github.com/xiaozhe7772222/dsh-api-key-pool) 的调度语义，为 DeepSeek Harness 0.1.1-rc.2 提供原生 Cordis/PiAiAdapter 号池接入。完整来源与差异见 [`UPSTREAM.md`](./UPSTREAM.md)。

## 接入布局

| 模式 | DSH_HOME | Profile | 端口 | 号池行为 |
| --- | --- | --- | --- | --- |
| 日常共存 | `.dsh` | `web` | 3080 | 单例加载；普通 Provider 透传，仅接管 `pool-*` |
| 隔离验收 | `.dsh-key-pool` | `web-key-pool` | 3081 | 单例加载；拒绝所有非 `pool-*` 请求 |

日常入口仍是原有 `MetaMath Harness.lnk` 与原生 3080；号池设置卡片位于 Free Search 下方。插件不修改官方包、原生 Provider 配置或原生启动脚本。独立 Profile 继续用于隔离测试与回滚。

## 启动与健康检查

```powershell
.\启动-DeepSeek-Harness-号池.ps1
```

无浏览器启动：

```powershell
.\启动-DeepSeek-Harness-号池.ps1 -NoBrowser
```

健康接口为 `http://127.0.0.1:3081/api/dsh-api-key-pool/health`，仅返回启用数量、可用数量、活动请求和冷却/熔断状态等脱敏统计。

## 配置与使用

1. 打开日常 3080 实例的“设置 → 插件 → API Key 号池”，点「添加号池」。
2. 按原生「设置 → 模型」的同一顺序填写：主字段是 **API 密钥**，一枚一枚填即可（点「添加密钥」或回车入队，一次粘贴多行也会自动拆开）；端点、协议、模型收在折叠的 **自定义设置** 里。
3. **模型目录** 与原生一致，一行一个模型：模型 ID + 显示名称 + 容量折叠（上下文窗口、最大输出 token，支持 `256K`、`1M` 写法）+ **识图（图片输入）** + 删除，底部「添加模型」逐行新增；勾选识图会声明 `input: [text, image]`，并通过 Harness 持久附件服务解析图片；不勾选则保持文本默认，不再用逗号把多个模型挤进一个输入框。
4. Provider ID 会随显示名或端点主机名自动派生，创建后固定不可改；点「保存」一次提交池配置与新 Key，已存储的 Key 以脱敏行显示轮询状态，可「重置」冷却或标记「移除」。
5. 为需要号池的模型选择对应的 `pool-*` Provider；原生 Provider、原生「设置 → 模型」页面与原生 Profile 均不受影响。

不要把真实 Key 写入仓库或普通配置文件：完整 Key 只在保存时上行一次进入 DSH Credentials，页面、接口与日志只有脱敏值和 keyId。插件支持 OpenAI、Anthropic、Google 与 Ollama 对应的 DSH `PiAiAdapter` 协议。单个流式请求会固定使用同一个 Key，流结束后才释放槽位。

## 失败策略

- 401/403：禁用当前 Key。
- 429/速率限制：当前 Key 进入有界冷却。
- 5xx/网络错误：累计后进入有界熔断。
- 调用方主动取消：释放槽位，不惩罚 Key。
- 全部 Key 不可用：返回明确错误，不无限重试。

## 开发验证

```powershell
cd plugins/dsh-api-key-pool
npm run check
npm test
```

测试覆盖调度公平性、并发槽、冷却/熔断、流式生命周期、持久图片附件、设置模型、100 路同值 Key 并发去重、并发挂池不丢更新、失败回滚、脱敏接口与远端源码凭据扫描。所有配置和凭据写入口由 Host 内的单队列串行化；只读状态与推理流不经过该队列。

## 回滚

从原生 Web Profile 移除本插件的 dependency/bundle 并重新安装即可撤销日常共存接入；保留号池 Credentials 与独立 `.dsh-key-pool` 验收环境。独立 Profile 的回滚仍只移除其自身接线，不删除用户凭据。

## 许可证

MIT，见 [`LICENSE`](./LICENSE)。
