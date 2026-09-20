# DSH Qoder 订阅插件

[English](./README.md) | 简体中文

`dsh-provider-qoder` 将你的 Qoder 订阅接入 DeepSeek Harness（DSH），支持文本与图片输入、流式文本、推理内容和工具调用，可选择国际版或中国区 Qoder 服务。

插件负责认证和模型通信，工具执行、工作区操作及权限管理由 DSH 负责。
本项目是社区适配插件。

## 功能

- 通过 Qoder Personal Access Token（PAT，个人访问令牌）配置订阅访问。
- 支持国际版（`global`）和中国区（`china`）服务。
- 获取账号可用模型，选择启用的模型，并在服务返回相关信息时显示价格倍率和推理强度选项。
- 支持流式回答、推理内容、多模态、搜索、工具调用及多轮交互。
- 在设置中查看账号信息、额度和重置时间。

## 安装

### 使用前提

你需要可运行的 DSH Web 环境、可用的 Qoder 订阅，以及与所选服务区域匹配的 PAT。运行插件的 DSH profile 必须提供托管凭据服务；通过设置页面配置时，凭据存储还需可写。

本包的依赖范围为 DSH 相关包 `>=0.1.2-rc.1 <0.2`、Cordis `>=4.0.2 <5` 和 React `^18.2.0`。设置界面还依赖宿主提供凭据远程接口和设置插槽，请使用具备这些接口的 DSH 版本；上述范围不代表每个版本都经过实测。

### 从 npm 安装

在终端执行：

```sh
dsh plugin --profile web add dsh-provider-qoder
```

## 配置与使用

### 1. 保存服务区域和 PAT

打开 DSH Web 的 **设置 → 模型**，找到页面底部的 **Qoder 凭据** 卡片，点击 **编辑**。

| 服务区域 | 对应账号 |
| --- | --- |
| 国际版（Global，默认） | `qoder.com` |
| 中国区（CN） | `qoder.com.cn` |

选择与账号一致的区域，将 Qoder PAT 填入界面标为 **API 密钥** 的输入框，然后点击 **保存**。

### 2. 获取并选择模型

1. 保存 PAT 和服务区域后，再次点击 **编辑**。
2. 展开 **自定义设置**，点击 **获取可用模型**。
3. 选择需要启用的模型，至少保留一个，然后点击 **保存**。
4. 在 DSH 的模型选择器中选择 Qoder 模型，开始对话。

获取模型使用的是**已保存的 PAT 和服务区域**。更换账号或区域后，需要重新获取模型。初始模型目录仅供候选参考，实际可用模型以账号查询结果为准。模型倍率、推理强度选项及图片输入能力由 Qoder 提供，并非所有模型都有这些信息。

展开模型选择器时会自动刷新已启用 Qoder 模型的元数据，成功获取后缓存 5 分钟。

### 3. 查看账号与额度

打开 **设置 → Qoder** 查看账号和额度。

## 常见问题

### 插件无法启动，或凭据无法保存

确认已重启安装插件的 profile，且该 profile 提供 DSH 托管凭据服务。如果提示存储不可写，需要在宿主侧配置可写的凭据存储。插件不会从环境变量读取 PAT。

### 已保存 PAT，但获取模型或请求失败

确认 PAT 有效且与已保存的服务区域匹配。修改后先保存，再获取模型。保存操作本身不会验证令牌。若账号额度已用尽，需先处理订阅额度问题。

### 切换区域后，模型仍不可用

Global 与 China 的模型目录会分别保存。切换区域不会自动替换 PAT，也不会自动重新获取该区域的模型；请先保存匹配区域的 PAT，再获取并保存所选区域的模型。

### 请求是否会自动重试？

模型生成重试由 DSH 管理。需要启用时，运行中的 profile 应包含 `@deepseek-ai/dsh-llm-retry`。插件使用 DSH 默认重试策略报告空响应、限流、服务端、超时和传输错误；认证、无效请求、取消、额度及协议格式错误默认不重试。Qoder transport 可以独立重试一次幂等的模型目录、订阅者资料或配额读取，但绝不会在内部重试模型生成 POST。

## 从源码安装与开发

在已安装 Git、Node.js 和 pnpm 的环境中执行。Node.js 需支持项目测试脚本使用的 `--experimental-strip-types` 和 `--test-isolation=none` 参数。

```sh
git clone https://github.com/mo-n/dsh-provider-qoder.git
cd dsh-provider-qoder
pnpm install --frozen-lockfile
pnpm run build
```

将构建后的仓库目录安装到 DSH profile。以下路径为占位示例，请替换为实际绝对路径：

```sh
dsh plugin --profile web add /absolute/path/to/dsh-provider-qoder
```

重启 profile 后，按前文完成配置。若在 DSH 源码工作区中运行 CLI，可使用该工作区的 `pnpm dsh` 命令。

开发时，在插件目录运行监听构建：

```sh
pnpm run dev
```

提交修改前运行：

```sh
pnpm run check
```

该命令运行模拟网络的非 UI 测试、构建 ESM 包与类型声明、检查构建产物并预览打包内容，不会发起真实 Qoder 模型请求或发布 npm 包。

## 参考项目

- [pi-provider-qoder](https://github.com/simonsmh/pi-provider-qoder) - Qoder 认证、API 通信及协议处理的参考实现。

## 反馈

请通过 [GitHub Issues](https://github.com/mo-n/dsh-provider-qoder/issues) 提交问题，附上插件和 DSH 版本、所选服务区域、复现步骤及脱敏后的错误信息。不要提交 PAT、短期令牌或个人账号信息。

本项目采用 MIT 许可证。
