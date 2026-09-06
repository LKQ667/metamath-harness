# dsh-connect-trae 开发说明

## 项目目标

本项目旨在实现一个可正常工作的 DSH Trae 接入版本。

开发路线不是直接照搬现有 Trae 项目，而是：

1. 以已经验证可用的 `dsh-workbuddy-connect` 为成功参考，研究其 DSH 接入架构和完整通信链路。
2. 以 `dsh-trae-api` 作为 Trae 侧实现资料和失败样本，定位其不可用的具体原因。
3. 将 WorkBuddy 项目中可复用的设计思想迁移到本项目，并针对 Trae 的进程、协议、认证、会话及消息机制进行适配。
4. 在本项目中完成实现和端到端验证，目标是真正可用，而非仅保持代码结构相似。

## 参考项目

三个项目位于同一个父目录下：

```text
DshProject/
├── dsh-connect-trae/       # 当前实现项目
├── dsh-workbuddy-connect/  # 已验证可用的成功参考
└── dsh-trae-api/           # Trae 侧参考及失败样本
```

参考仓库：

- WorkBuddy 成功参考：<https://github.com/corrinehu/dsh-workbuddy-connect>
- Trae API 参考：<https://github.com/Wang-JQ77/dsh-trae-api>
- 当前目标项目：<https://github.com/dingminhua/dsh-connect-trae>

## 开源合规要求

本项目参考了上述与 Trae 接入直接相关的开源项目，必须遵守各自的许可证规范：

- **Trae 相关参考项目清单**：见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，包含与 Trae 接入直接相关的架构/协议参考项目的许可证说明。
- **引入新的 Trae 相关依赖时**：必须在 `THIRD_PARTY_NOTICES.md` 中登记其名称、用途与许可证，并随包携带上游 LICENSE（直接依赖随 npm 安装自带；若手工引入第三方源码，需将许可证文本一并纳入项目）。
- **复用参考项目代码时**：本项目当前仅借鉴架构思路、不整体复制源码（关键模块均为独立实现并在注释中标注参考来源）。若未来改为直接复制或派生某个上游文件的代码，须保留该文件的版权声明与许可证头，并在 `THIRD_PARTY_NOTICES.md` 中注明。
- **发布时**：`package.json` 的 `files` 白名单已包含 `THIRD_PARTY_NOTICES.md`，第三方声明随 npm 包一起分发。

## 研究重点

后续分析至少覆盖以下方面：

- DSH 插件或连接器的启动与注册方式
- 宿主进程发现、启动、重连和退出处理
- 请求与响应协议以及流式事件传递
- 会话创建、恢复、取消和状态同步
- 认证信息、配置与环境变量的处理
- 工具调用及其结果回传
- 错误处理、超时、日志和诊断能力
- WorkBuddy 与 Trae 在接口和运行机制上的差异
- `dsh-trae-api` 当前失败链路及根因

## 实施原则

- 先对比并绘制三个项目的关键调用链，再确定实现方案。
- 复用 WorkBuddy 项目的架构思路，而不是未经验证地逐文件复制。
- 所有移植点都必须结合 Trae 的真实行为进行适配。
- 每个关键结论应附有代码位置、运行日志或测试结果作为依据。
- 最终以端到端可运行和可重复验证作为完成标准。

## 对外发布基准

对外 README、npm 包组织、发布文档和发布操作，以团队自己的项目 `dsh-subagent-default-model` 为主要基准：

- 本机参考目录：`../dsh-subagent-default-model`
- GitHub：<https://github.com/dingminhua/dsh-subagent-default-model>
- 根 README：用于 GitHub 项目主页，包含项目定位、亮点、工作原理、截图、安装、配置、开发、卸载、许可证和徽章。
- npm README：包目录内提供中文 `README.md` 与英文 `README.en.md`。
- 发布记录：维护包内 `CHANGELOG.md`。
- 发布流程：项目根目录维护 `RELEASING.md`，作为唯一权威发布说明。
- npm 元数据：完整维护 description、keywords、author、license、repository、homepage、bugs、engines、exports、files、DSH bundle/client 声明。
- 发布包白名单：通过 `files` 明确限定构建产物、产品截图、bundle patch、双语 README、CHANGELOG、第三方声明和 LICENSE。
- 发布前验证：测试、构建、`npm pack --dry-run`、版本与 CHANGELOG 核对。
- 发布后验证：核对 npm `version` 与 `dist-tags.latest`，并验证 DSH 从 npm 安装后的实际加载。
- GitHub 发布形态：使用版本提交和带说明的 annotated tag，tag 必须指向包含对应代码与版本号的提交。

`dsh-subagent-default-model` 只作为**对外展示和发布工程**的基准；`dsh-connect-trae` 的内部模块划分、协议适配、安全边界和测试结构根据 Trae 接入需求独立设计，以 `docs/IMPLEMENTATION_PLAN.md` 为准。任何真实发布、Git push、tag 或 npm publish 都必须在用户明确确认后执行。

## 本地模型目录策略

当Trae模型发现接口因版本或私有认证封装不可用时，Provider使用版本化的本地静态模型目录。目录只能收录本机Trae日志、UI选择器或MetadataHandler中实际观察到的模型，并记录来源、观察时间和置信度。

模型能力按“模型ID + function/Agent模式”记录，因为同一模型在`solo_work_lite`与`solo_agent_lite`下可能具有不同上下文窗口、输出上限和功能。思考强度只有在模型元数据明确给出`reasoning_effort_options/default_reasoning_effort`时才列出具体档位；UI仅显示selector时只记录`reasoningSupported: true`，不得虚构档位。

当前已确认的低成本测试模型为`DeepSeek-V4-Flash-Official`，显示名`DeepSeek-V4-Flash 正式版`，在`solo_work_lite`日志中确认输入窗口168000、非多模态、支持reasoning功能入口。
