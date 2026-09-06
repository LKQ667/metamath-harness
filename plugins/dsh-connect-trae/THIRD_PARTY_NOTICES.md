# 第三方开源声明（Third-Party Notices）

> 本文件只记录与 Trae 接入直接相关的开源项目及其许可证，确保符合各上游项目的开源许可要求（署名保留、许可文本随分发携带等）。通用平台与构建依赖（`@deepseek-ai/*`、`react`、`typescript`、`tsdown`、`vitest` 等）的许可证随各自 npm 包自动携带，不属于本文档记录范围。若你对本文件的完整性有疑问或发现遗漏，请提交 issue 或 PR。

## 与 Trae 接入相关的参考项目

本项目在设计与实现过程中参考了以下与 Trae 接入直接相关的开源项目，主要用于**架构模式与上游协议研究**。参考方式为"借鉴设计思路 + 独立实现"，未整体复制其源码（关键模块均为本项目独立编写，并在源码注释中标注了所参考的既有模式）。这些项目的版权属于其各自的作者，本项目代码不构成对它们的再分发。

| 参考项目 | 仓库 | 参考内容 | 许可证 |
| --- | --- | --- | --- |
| `dsh-trae-api` | <https://github.com/Wang-JQ77/dsh-trae-api> | Trae 上游协议（认证、会话、模型目录）的参考与失败样本分析（见 `docs/ANALYSIS.md`、`docs/ANALYSIS_CONCLUSION.md`、`docs/SOLO_ROUTE_DECISION.md`） | MIT |
| `laojichao/trae-local-api` | <https://github.com/laojichao/trae-local-api> | `dsh-trae-api` 的直接上游，仅作为 Trae 协议调研线索，本项目未复用其代码（见 `docs/SOLO_ROUTE_DECISION.md`） | 未声明（保留所有权利） |

## 合规说明

- `dsh-trae-api` 使用 **MIT** 宽松许可，与项目自身的 MIT 许可证兼容；`laojichao/trae-local-api` 未声明许可证（保留所有权利），本项目仅将其作为协议调研线索，未复制、修改或分发其代码。
- MIT 许可要求保留上游版权声明。本项目**不重新打包或再分发**上述参考项目的源码，仅参考其架构思路与协议信息；`docs/` 中的分析文档亦为独立撰写。
- 若后续引入新的与 Trae 接入相关的依赖或复用其他项目的代码，必须在引入时同步更新本文件，并遵守对应许可证的署名与声明要求。
