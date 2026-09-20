# 升级保护地图

依据根目录三文档与 2026-09-08 接线检查提炼。这是风险导航，不是永久版本锁或现状证明；每轮结合当前文件更新本轮报告。历史记录已撤销的做法不得重新激活。

## 识图：三个独立链路都要保护

1. **自定义模型识图开关**：`scripts/patch-settings-models-vision.py` → 官方 `dsh-client-ui-settings-models/lib/client.js`。GOAL-20260823-53 的手工补丁在升级中丢失，GOAL-20260906-76 已脚本化。先从实际 CLI/安装解析链定位目标，传显式路径执行 `python scripts/patch-settings-models-vision.py --check <client.js>`；确认新版未原生吸收后去掉 `--check` 重放。脚本默认绝对路径只适用于原机器，不能照搬。
   - 当前脚本的“在位”分支只判断 `modelVision` 字符串，不能证明完整性；核对 JSX、中文/英文 locale、写入逻辑，执行语法检查和浏览器双向保存/回读。二次运行哈希不变；锚点失配不能强行套旧产物。
   - 自定义提供方容量区有复选框；勾选保存 `input: [text, image]`，取消删除字段恢复继承，不强制改成 text；官方 DeepSeek 专用编辑器不增加此开关；其他提供方同名模型不受影响。测试后恢复原配置。
2. **工具与附图**：`plugins/dsh-mathmodel/src/{vision,tools,host,typert-shared}.js`、`src/client-bundle.cjs`、`test/vision.test.mjs`、`.dsh/skills/claude-vision-skill/`。
   - 保留手动“附图分析（N 张）”→工作区安全落盘→相对路径进入可编辑草稿→用户发送→按需 `vision_analyze`；失败不损坏原图/草稿，不自动发送或自动调用收费视觉服务。技能不能因 Key 已配置而永久隐藏（GOAL-28/30 撤销旧行为）。
   - GOAL-20260906-77：无扩展名的内容寻址 PNG/JPEG/GIF/WebP 必须按字节签名识别；截断/扩展名冲突失败关闭，错误脱敏，工具失败后不得猜图。覆盖真实附件解析、工作区边界与缺凭据失败路径。
   - 历史受管 Key 列表不是现有凭据事实；后续记录已删除 DASHSCOPE_API_KEY，不能恢复、复制旧值或宣称收费识图可用。
3. **号池图片输入**：`plugins/dsh-api-key-pool/src/{adapter,host,schema}.js`。验证 UI→Typert→settings→Host→PiAiAdapter→官方持久附件 resolver 全链；仅勾选框存在不算完成。文本模型仍拒绝图片；保留单 Host 写队列、并发去重、单流 Key 固定和失败精确补偿，普通 Provider 不受干扰。

## 会话深链：不能因启动报错直接移除

现有 Profile 固定 `dsh-session-link@0.1.4`，`pnpm-workspace.yaml` 同时声明版本绑定 patch 和官方 `session-reference` override；升级时重新核定这些坐标，不永久锁死旧 DSH。

`patches/dsh-session-link@0.1.4.patch` 的三个意图必须保留或由新版等效替代：

- `cordis.patch.yml` 去掉重复 session-reference insert，官方服务与 session-link 各单例。
- `lib/client.js` 通过 `slots.inject` 等待插槽声明，避免直接 register 的加载时序错误。
- `lib/index.js` 提供 `/s/<单段 id>` 的 SPA 入口；本机回放 `/` 时转发原 Host/Cookie、沿用官方认证，不改成公共免认证页面。

GOAL-20260906-76：`assertNever` 曾因旧 session-reference 被错误解析而失配。先核对全局 DSH 所带版本、Profile 实际解析和 API，再适配 override；不能据报错一句话断定功能无法共存。

验收：复制按钮→实际剪贴板 `dsh://session/<id>`→切换到另一会话→访问 `/s/<id>`→目标会话选中及标题正确；另验跨会话引用仍由官方 resolver 提供。未认证不能获得完整页面，非法 `/s/a/b` 拒绝；旧基线分别为 401/404，合法认证 200，上游异常 502，新版状态变化须说明等效性。没有控制台插件错误。可参考 `Overall-goal/goal-76/scripts/e2e_session_link.mjs`（先核实文件位置和实现适配）。

`dsh://` 操作系统协议注册与浏览器深链分开验收；前者是可选注册表操作，不自动执行 `register-protocol.ps1`，未注册不冒充已通过。

## 其他覆盖风险

| 保护对象 | 定位与不可丢失行为 |
| --- | --- |
| 品牌/布局 | 根 `MetaMath-Harness.ico` 的升级前后 SHA-256 相同；实际构建入口为 `plugins/dsh-mathmodel/scripts/build.mjs`，从根 ICO 内嵌。展开/收起侧栏、favicon、快捷方式一致，“大道至简”保留。适配新插槽而非换回官方图标。 |
| Header/工作台 | `src/client-bundle.cjs` 的 Session log 唯一选择器、下载、aria 属性及卸载恢复；better-sidebar 的宽度变量、collapsed/host 标记；展开收起、非空/空会话下按钮不重叠，不能靠全局 CSS 放宽匹配。 |
| Skill/Preset | 全部现存 `.dsh/skills/`、sidecar、模板/门禁/共享论文 catalog、`.dsh/.agent-presets/`，不只备份旧 README 的十二项；卡片确认只写草稿、取消不写、用户手动发送，目录与说明正常。检查其他 Agent 副本与链接是否过期。 |
| API 迁移 | GOAL-20260904-74：skills 从旧 connection API 转向 `remote.skills`，皮肤改用新平台种子服务；按新版实际签名/信封校验，不用旧包补缺失导出。 |
| 生图/PPT | 生图连接与当前选择保留，`image_generate` 工具及 Toolview 不重名；订阅只经 `subscriptionSessions` 读取内存会话。`editable_ppt_image` 保留 dsh-current 锁定、Codex 禁用、无跨连接回退及路径/MIME/元数据门禁，CLI 安装指向工作区源码。 |
| 皮肤/壁纸 | `plugins/dsh-client-ui-skins/lib/` 是登记过的本地派生实现，含 FX 与壁纸，不能因为目录名是 lib 就删除或换 npm 原版；本轮若新增源码构建链，先证明可重建等价。浏览器 localStorage 保留，不以清站点数据“修复”升级。 |
| 第三方模型插件 | 按当前 Profile 动态枚举；保护 WorkBuddy 双文件名探测补丁、Trae lastCatalog 元数据、AGY 用户层 agyBin/配置、订阅 service/工具去重 patch；不覆盖用户配置，不恢复已退出的 llm-oauth 或未安装的 ZCode。 |
| 桌宠/知识库 | 桌宠包安全导入源码补丁、用户 main-config 与原创动画保留；素材独立许可。SQLite 保留数据路径、FTS5 和 ask 门控，停用插件不删除数据库。 |
| 启动/认证 | `启动-MetaMath-Harness.ps1` 的 DSH_HOME、实际 CLI 路径、隐藏启动、端口复用、--no-open/-NoBrowser、token URL 逻辑；不能仅有旧 cookie 时验收，必须覆盖冷启动后新 token。不得把 token 写入报告。 |
| 发行层（仅分发任务） | 本地通过不等于 staging 通过；中文 PowerShell 5.1 脚本保留 UTF-8 BOM，npm/pnpm stderr 合流，检查退出码；skins/free-search 等安装脚本不重建的 lib 必须携带。禁递归展开 Junction；便携 data 保留；论文 catalog 哈希与许可/脱敏检查通过后才发布。 |

## 已知文档漂移：必须核实，不默认丢弃

- 维护范式称仅识图一项在册热补丁，但 README §3.9/GOAL-46/50/72 仍记录重试 6 次，GOAL-51 记录 opencode-go 目录热修。每轮核实当前官方实现与实际运行值，分别标明“仍需保留 / 已被上游吸收 / 失效待适配”。仍需保留的旧热修应先固化为幂等脚本、登记和门禁，不能盲目复制旧 pi-ai 数据或全局替换常量；认证失败不改成无限重试。
- 2026-09-08 当前 Profile/patch 已使用 subscriptions 0.6.0，三文档部分段落仍写 0.5.2。用实际包、锁文件和补丁绑定核实，而非照旧文档降级。
- 当前 Profile 还有 `dsh-opencode-session`，不在三文档现有主要清单中。先保护其本地目录与接线，再核实来源、边界、版本门和测试；未知不等于可删。以后新增插件同样处理。
- 用户给出的 TraeWork CN 2026/9/6 19:19:23 标识在本轮未找到正文；上述结论来自三文档和所列文件，不代表已读取该对话。
